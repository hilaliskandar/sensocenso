import streamlit as st
import pandas as pd
from pathlib import Path
import io
import re

from config.config_loader import get_settings, get_page_config
from censo_app.transform import (
    carregar_sp_idade_sexo_enriquecido as carregar_base,
    filtrar_situacao_tipo,
    agregar_categorias,
    categorias_para_percentual,
)
from censo_app.viz import construir_grafico_pizza, construir_grafico_barra
from censo_app.labels import apply_simplify_and_wrap as _apply_labels
from censo_app.ui_utils import ensure_abnt_css, dataframe_to_csv_download

st.set_page_config(page_title="Domicílios", layout="wide", initial_sidebar_state="collapsed")

# CSS: legendas ABNT com altura uniforme e quebra de linha
ensure_abnt_css(height_caption_px=64)

SETTINGS = get_settings()

# Decodificação de Tipo de Setor (mesma lógica da Demografia)
_TIPO_MAP_DEFAULT = {
    0: "Não especial",
    1: "Favela e Comunidade Urbana",
    2: "Quartel e base militar",
    3: "Alojamento / acampamento",
    4: "Setor com baixo patamar domiciliar",
    5: "Agrupamento indígena",
    6: "Unidade prisional",
    7: "Convento / hospital / ILPI / IACA",
    8: "Agrovila do PA",
    9: "Agrupamento quilombola",
}
try:
    DEMOG_CFG = get_page_config('demografia') or {}
    cfg_types = DEMOG_CFG.get('sector_types') if isinstance(DEMOG_CFG, dict) else None
    if isinstance(cfg_types, dict) and cfg_types:
        TIPO_MAP = {int(k): str(v) for k, v in cfg_types.items()}
    else:
        TIPO_MAP = _TIPO_MAP_DEFAULT
except Exception:
    TIPO_MAP = _TIPO_MAP_DEFAULT

# Helper: quebra de linha em rótulos de categorias para evitar truncamento
def _wrap_label(text: str, width: int = 16, br: str = "<br>") -> str:
    if not isinstance(text, str):
        text = str(text) if text is not None else ""
    words = text.split()
    if not words:
        return ""
    lines = []
    cur = words[0]
    for w in words[1:]:
        if len(cur) + 1 + len(w) <= width:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return br.join(lines)

def _extract_root_from_title(title: str) -> list[str]:
    """Deriva candidatos de raiz a partir do título (antes/depois de travessão, sem termos genéricos)."""
    if not isinstance(title, str) or not title:
        return []
    t = title.strip()
    # separar por travessão e hífen
    parts = re.split(r"\s*[—–\-:]\s*", t)
    cands = {t}
    for p in parts:
        p = p.strip()
        if p:
            cands.add(p)
    # remover prefixos genéricos
    cleaned = set()
    for c in cands:
        cc = re.sub(r"^(Quantidade|Número|Percentual|Proporção|Tipo)\s+de\s+", "", c, flags=re.IGNORECASE).strip()
        cleaned.add(cc)
    # ordenar por tamanho decrescente (preferir frases mais longas)
    return sorted({x for x in cleaned if len(x) >= 8}, key=len, reverse=True)

def _dominant_label_prefix(labels: pd.Series) -> str:
    """Encontra o prefixo dominante (antes da primeira vírgula) nas categorias, se houver maioria."""
    try:
        first_parts = (
            labels.dropna().astype(str).str.split(",", n=1).str[0].str.strip()
        )
        if first_parts.empty:
            return ""
        vc = first_parts.value_counts()
        top = vc.index[0] if not vc.empty else ""
        freq = int(vc.iloc[0]) if not vc.empty else 0
        if freq >= max(2, int(0.5 * len(first_parts))):  # maioria simples
            return str(top)
        return ""
    except Exception:
        return ""

def _strip_known_boilerplate(s: str) -> str:
    """Remove termos recorrentes não informativos nas categorias."""
    if not s:
        return s
    out = s
    # Redução específica: "Destinação do esgoto ... é <categoria>" -> manter apenas <categoria>
    # e tratar caso de inexistência: "sem banheiro nem sanitário"
    try:
        # Normaliza espaços
        out = re.sub(r"\s+", " ", out).strip()
        # Caso especial: inexistente
        patt_inexist = re.compile(
            r"^(?:Domicílios\s+Particulares\s+Permanentes\s+Ocupados,\s*)?Destina[cç][aã]o\s+do\s+esgoto\s+inexistente,\s*pois\s+n[aã]o\s+tinham\s+banheiro\s+nem\s+sanit[áa]rio\.?$",
            flags=re.IGNORECASE,
        )
        if patt_inexist.match(out):
            return "sem banheiro nem sanitário"
        # Remover prefixo longo e manter apenas o que vem após "é"
        patt_prefix = re.compile(
            r"^(?:Domicílios\s+Particulares\s+Permanentes\s+Ocupados,\s*)?Destina[cç][aã]o\s+do\s+esgoto\s+do\s+banheiro\s+ou\s+sanit[áa]rio\s+ou\s+buraco\s+para\s+deje[cç][oõ]es\s*(?:é\s*)",
            flags=re.IGNORECASE,
        )
        out = patt_prefix.sub("", out)
    except Exception:
        pass
    # normalizar sufixos como _1 ao final
    out = re.sub(r"_(\d+)\s*$", "", out)
    # remover conectivos comuns
    out = re.sub(r"^\s*Com\s+", "", out, flags=re.IGNORECASE)
    out = re.sub(r"\s+no\s+domic[ií]lio\s*$", "", out, flags=re.IGNORECASE)
    out = re.sub(r"^Tipo\s+de\s+esp[eé]cie\s+é\s+", "", out, flags=re.IGNORECASE)
    # compactar "10 ou mais" -> "10+"
    out = re.sub(r"\b(\d{1,2})\s+ou\s+mais\b", r"\1+", out, flags=re.IGNORECASE)
    # Redução agressiva para 'banheiro(s) de uso exclusivo com chuveiro e vaso sanitário ...'
    # Exemplos alvo:
    #   '1 banheiro de uso exclusivo com chuveiro e vaso sanitário existentes no domicílio'
    #   '9+ banheiros de uso exclusivo com chuveiro e vaso sanitário existentes no domicílio'
    pattern_banheiro = re.compile(
        r"^\s*(\d{1,2}\+?)\s+banheiros?\s+de\s+uso\s+exclusivo\s+com\s+chuveiro\s+e\s+vaso\s+sanit[áa]rio\s+(?:existentes\s+no\s+domic[ií]lio)?\s*$",
        flags=re.IGNORECASE,
    )
    m = pattern_banheiro.match(out)
    if m:
        out = m.group(1)
        return out
    # espaços
    out = re.sub(r"\s{2,}", " ", out).strip()
    # capitalização leve: manter como está para não interferir em siglas
    return out

def _simplify_label_by_roots(label: str, roots: list[str]) -> str:
    if not isinstance(label, str):
        label = str(label) if label is not None else ""
    s = label.strip()
    if not s:
        return s
    for r in roots:
        if not r:
            continue
        # tentar remover no início seguido de pontuação ou espaço
        pattern = re.compile(rf"^\s*(?:{re.escape(r)}\s*[,.:;\-–—]\s*)(.+)$", flags=re.IGNORECASE)
        m = pattern.match(s)
        if m:
            s = m.group(1).strip()
            break
        # ou se começar exatamente com r
        if s.lower().startswith(r.lower()):
            rest = s[len(r):].lstrip(" ,.:;\-–—")
            s = rest.strip() or s
            break
    # limpeza adicional
    s = _strip_known_boilerplate(s)
    return s

def _apply_simplify_and_wrap(df_in: pd.DataFrame, titulo: str, width: int = 18) -> pd.DataFrame:
    df = df_in.copy()
    # candidatos a raiz vindos do título e do prefixo dominante das categorias
    roots_from_title = _extract_root_from_title(titulo)
    dom_prefix = _dominant_label_prefix(df.get("categoria", pd.Series(dtype=str)))
    roots = roots_from_title + ([dom_prefix] if dom_prefix else [])
    # incluir versões "reduzidas" que aparecem muito nos rótulos
    extra_roots = [
        "Domicílios Particulares Permanentes Ocupados",
        "Domicílios Particulares Improvisados Ocupados",
        "Unidades de Habitação em Domicílios Coletivos Com Morador",
    ]
    for er in extra_roots:
        if er not in roots:
            roots.append(er)
    # simplificação + wrap
    df["categoria_simplificada"] = df["categoria"].apply(lambda x: _simplify_label_by_roots(x, roots))
    df["categoria_wrapped"] = df["categoria_simplificada"].apply(lambda s: _wrap_label(s, width))
    return df

@st.cache_data(show_spinner=False)
def carregar_df():
    parquet = SETTINGS.get("paths", {}).get("parquet", "data/sp.parquet")
    excel_rm = SETTINGS.get("paths", {}).get("rm_xlsx", "insumos/Composicao_RM_2024.xlsx")
    df = carregar_base(parquet, limite=None, detalhar=False, uf="35", caminho_excel=excel_rm)
    return df

@st.cache_data(show_spinner=False)
def ler_grupos():
    """Carrega configuração de grupos (se existir). Retorna dict vazio se ausente/erro."""
    try:
        import yaml
        p = Path("config/categorias.yaml")
        if not p.exists():
            return {}
        with p.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        if not isinstance(cfg, dict):
            return {}
        return cfg
    except Exception:
        return {}

def _fmt_mun(cd: str|None, lookup: pd.DataFrame):
    if not cd:
        return "(selecione)"
    row = lookup.loc[lookup["CD_MUN"].astype(str)==str(cd)]
    if row.empty:
        return str(cd)
    return f"{row.iloc[0]['NM_MUN']} ({row.iloc[0]['CD_MUN']})"

df = carregar_df()
_cfg = ler_grupos() or {}
grupos = (_cfg.get("groups") or [])
palette = (_cfg.get("palette") or [])
fig_list: list[str] = []

st.checkbox("Comparar tipos de domicílio (DPPO × DPIO × DCCM) quando disponível", value=False, key="cmp_tipos")

st.title("Domicílios — Indicadores Categóricos")

with st.sidebar:
    st.subheader("Filtros")
    sit_opts = sorted(df.get("SITUACAO", pd.Series(dtype=str)).dropna().unique().tolist()) or ["Urbana","Rural"]
    tipos_presentes = sorted(pd.to_numeric(df.get("CD_TIPO"), errors="coerce").dropna().unique().astype(int).tolist())
    sel_sit = st.multiselect("Situação", options=sit_opts, default=sit_opts)
    # Opções com rótulos (código — descrição)
    tipo_opts = [(k, TIPO_MAP.get(k, str(k))) for k in tipos_presentes]
    sel_tipos_pairs = st.multiselect(
        "Tipo de Setor",
        options=tipo_opts,
        default=tipo_opts,
        format_func=lambda x: f"{x[0]} — {x[1]}",
    )
    sel_tipos = [k for k, _ in sel_tipos_pairs] if sel_tipos_pairs else tipos_presentes
    nivel = st.selectbox("Nível", ["Estado","RM/AU","Região Intermediária","Região Imediata","Município","Setores"], index=4)

df_filt = filtrar_situacao_tipo(df, sel_sit, sel_tipos)

# Escopo geográfico (mesma lógica da Demografia, versão compacta)
title_suffix = "Estado de São Paulo"
if nivel == "RM/AU" and "NOME_RM_AU" in df_filt.columns:
    nomes = sorted(df_filt["NOME_RM_AU"].dropna().unique().tolist())
    sel = st.selectbox("Região (RM/AU)", nomes)
    df_scope = df_filt[df_filt["NOME_RM_AU"].eq(sel)]
    title_suffix = sel
elif nivel == "Região Intermediária" and "NM_RGINT" in df_filt.columns:
    nomes = sorted(df_filt["NM_RGINT"].dropna().unique().tolist())
    sel = st.selectbox("Região Intermediária", nomes)
    df_scope = df_filt[df_filt["NM_RGINT"].eq(sel)]
    title_suffix = sel
elif nivel == "Região Imediata" and "NM_RGI" in df_filt.columns:
    nomes = sorted(df_filt["NM_RGI"].dropna().unique().tolist())
    sel = st.selectbox("Região Imediata", nomes)
    df_scope = df_filt[df_filt["NM_RGI"].eq(sel)]
    title_suffix = sel
elif nivel == "Município" and {"CD_MUN","NM_MUN"} <= set(df_filt.columns):
    mun_df = df_filt[["CD_MUN","NM_MUN"]].dropna().drop_duplicates()
    sel_mun = st.selectbox("Município", [None]+mun_df["CD_MUN"].tolist(), format_func=lambda x: _fmt_mun(x, mun_df))
    if sel_mun:
        df_scope = df_filt[df_filt["CD_MUN"].astype(str).eq(str(sel_mun))]
        title_suffix = _fmt_mun(sel_mun, mun_df)
    else:
        st.stop()
elif nivel == "Setores" and "CD_SETOR" in df_filt.columns:
    set_opts = sorted(df_filt["CD_SETOR"].dropna().unique().tolist())
    sel_set = st.selectbox("Setor", set_opts)
    df_scope = df_filt[df_filt["CD_SETOR"].eq(sel_set)]
    title_suffix = f"Setor {sel_set}"
else:
    df_scope = df_filt

# Determinar comparador dinâmico: para Município usar RM/AU (preferência) ou Região Imediata; senão, Estado
comp_df = df_filt
comp_title = "Estado de São Paulo"
try:
    if nivel == "Município" and isinstance(df_scope, pd.DataFrame) and not df_scope.empty:
        if {"TIPO_RM_AU", "NOME_RM_AU"} <= set(df_scope.columns):
            pairs = df_scope[["TIPO_RM_AU", "NOME_RM_AU"]].dropna().drop_duplicates()
            if not pairs.empty:
                t = str(pairs.iloc[0]["TIPO_RM_AU"]).upper()
                n = str(pairs.iloc[0]["NOME_RM_AU"])
                mask = (
                    df_filt["TIPO_RM_AU"].astype(str).str.upper().eq(t)
                    & df_filt["NOME_RM_AU"].astype(str).eq(n)
                ) if {"TIPO_RM_AU", "NOME_RM_AU"} <= set(df_filt.columns) else pd.Series([False] * len(df_filt))
                _dfc = df_filt[mask] if mask.any() else pd.DataFrame(columns=df_filt.columns)
                if not _dfc.empty:
                    comp_df = _dfc
                    comp_title = f"{t} — {n}"
        if comp_df is df_filt or comp_df.empty:
            if "RM_NOME" in df_scope.columns and df_scope["RM_NOME"].notna().any():
                n = str(df_scope["RM_NOME"].dropna().unique()[0])
                comp_df = df_filt[df_filt["RM_NOME"].astype(str).eq(n)] if "RM_NOME" in df_filt.columns else df_filt
                comp_title = f"RM — {n}"
            elif "AU_NOME" in df_scope.columns and df_scope["AU_NOME"].notna().any():
                n = str(df_scope["AU_NOME"].dropna().unique()[0])
                comp_df = df_filt[df_filt["AU_NOME"].astype(str).eq(n)] if "AU_NOME" in df_filt.columns else df_filt
                comp_title = f"AU — {n}"
            elif "NM_RGI" in df_scope.columns and df_scope["NM_RGI"].notna().any():
                r = str(df_scope["NM_RGI"].dropna().unique()[0])
                comp_df = df_filt[df_filt["NM_RGI"].astype(str).eq(r)] if "NM_RGI" in df_filt.columns else df_filt
                comp_title = f"Região Imediata — {r}"
except Exception:
    comp_df = df_filt
    comp_title = "Estado de São Paulo"

# Comparador (opcional): mesmo recorte escolhido acima, comparado ao Estado em %
col_esq, col_dir = st.columns(2)
with col_esq:
    st.caption("Selecionado (absoluto)")
with col_dir:
    st.caption(f"Comparador (em %) — {comp_title}")

for grupo in grupos:
    cols = [c for c in grupo.get("columns", []) if c in df_scope.columns]
    if not cols:
        continue
    titulo = grupo.get("title", "Indicador")
    chart = grupo.get("chart", "bar")
    # Agregações reutilizando transform
    base_comp = agregar_categorias(comp_df, cols)  # comparador (após filtros)
    base_comp = categorias_para_percentual(base_comp)  # comparador em %
    base_sel = agregar_categorias(df_scope, cols)   # seleção em absoluto
    # Se nível é Município e não há linhas do município para este grupo, pular variável inteira
    try:
        is_municipio = (nivel == "Município")
        if is_municipio and base_sel.empty:
            continue
    except Exception:
        pass
    # Simplificar rótulos (remove raiz do título) e aplicar wrap
    base_comp = _apply_labels(base_comp, titulo, width=18)
    base_sel = _apply_labels(base_sel, titulo, width=18)
    if palette:
        # aplicar rotação de cores para manter consistência
        import itertools
        colors = list(itertools.islice(itertools.cycle(palette), max(len(base_comp), len(base_sel))))

    with st.container():
        st.subheader(titulo)
        c1, c2 = st.columns(2)
    # Invertido: Selecionado (absoluto) à esquerda, Comparador (%) à direita
        with c1:
            if not base_sel.empty:
                st.markdown(
                    f"<div class='abnt-figure'><div class='abnt-caption'><strong>{titulo} — {title_suffix}</strong></div></div>",
                    unsafe_allow_html=True,
                )
                if chart == "pie" and len(base_sel) <= 8:
                    fig2 = construir_grafico_pizza(base_sel, categoria_col="categoria_wrapped", titulo=None)
                    if palette:
                        cols_apply2 = colors[:len(base_sel)]
                        fig2.update_traces(marker=dict(colors=cols_apply2))
                else:
                    fig2 = construir_grafico_barra(base_sel, categoria_col="categoria_wrapped", titulo=None)
                    if palette:
                        cols_apply2 = colors[:len(base_sel)]
                        fig2.update_traces(marker=dict(color=cols_apply2))
                fig2.update_layout(height=360, margin=dict(l=160, r=10, t=10, b=10))
                fig2.update_yaxes(automargin=True)
                if chart == "pie":
                    fig2.update_traces(textposition='outside')
                st.plotly_chart(fig2, use_container_width=True, key=f"dom_{grupo.get('id', titulo)}_sel")
                st.caption("Fonte: Elaboração própria com dados do Censo Demográfico 2022 (IBGE).")
                # download CSV (Seleção)
                fname2 = f"selecionado_{titulo.replace(' ', '_')}.csv".replace('—','_').replace('–','-')
                dataframe_to_csv_download(
                    base_sel,
                    file_name=fname2,
                    label="Baixar CSV (Selecionado)",
                    rename={"categoria_simplificada":"Categoria","valor":"Valor"},
                    columns=["Categoria","Valor"],
                )
        with c2:
            if not base_comp.empty:
                # Legenda ABNT com altura fixa (multilinha)
                st.markdown(
                    f"<div class='abnt-figure'><div class='abnt-caption'><strong>{titulo} — {comp_title} (%)</strong></div></div>",
                    unsafe_allow_html=True,
                )
                if chart == "pie" and len(base_comp) <= 8:
                    fig = construir_grafico_pizza(base_comp, categoria_col="categoria_wrapped", titulo=None)
                    if palette:
                        cols_apply = colors[:len(base_comp)]
                        fig.update_traces(marker=dict(colors=cols_apply))
                else:
                    fig = construir_grafico_barra(base_comp, categoria_col="categoria_wrapped", titulo=None)
                    if palette:
                        cols_apply = colors[:len(base_comp)]
                        # Bar traces: per-point color via marker.color
                        fig.update_traces(marker=dict(color=cols_apply))
                # Altura fixa para comparabilidade
                fig.update_layout(height=360, margin=dict(l=160, r=10, t=10, b=10))
                fig.update_yaxes(automargin=True)
                # Pie: rótulos para fora para evitar corte
                if chart == "pie":
                    fig.update_traces(textposition='outside')
                st.plotly_chart(fig, use_container_width=True, key=f"dom_{grupo.get('id', titulo)}_estado")
                st.caption("Fonte: Elaboração própria com dados do Censo Demográfico 2022 (IBGE).")
                # download CSV (Comparador)
                fname1 = f"comparador_{titulo.replace(' ', '_')}.csv".replace('—','_').replace('–','-')
                dataframe_to_csv_download(
                    base_comp,
                    file_name=fname1,
                    label="Baixar CSV (Comparador)",
                    rename={"categoria_simplificada":"Categoria","valor":"Valor"},
                    columns=["Categoria","Valor"],
                )

        # Tabela por grupo — apenas Município (sem comparativo)
        try:
            if nivel == "Município" and not base_sel.empty:
                tot_sel = float(base_sel["valor"].sum()) if not base_sel.empty else 0.0
                muni_tbl = base_sel[["categoria_simplificada","valor"]].rename(columns={"categoria_simplificada":"Categoria","valor":"Município"}).copy()
                if tot_sel > 0:
                    muni_tbl["Município (%)"] = (muni_tbl["Município"].astype(float) / tot_sel * 100.0).round(1)
                else:
                    muni_tbl["Município (%)"] = 0.0
                muni_tbl = muni_tbl.sort_values("Município", ascending=False)
                zero_note = " — total=0 (sem ocorrências)" if tot_sel == 0 else ""
                with st.expander(f"Tabela — {titulo} (Município{zero_note})", expanded=False):
                    st.dataframe(muni_tbl, use_container_width=True)
                    csv_muni = muni_tbl.to_csv(index=False).encode("utf-8-sig")
                    fname_muni = f"tabela_municipio_{titulo.replace(' ', '_')}.csv".replace('—','_').replace('–','-')
                    st.download_button("Baixar Tabela (CSV)", data=csv_muni, file_name=fname_muni, mime="text/csv")
        except Exception:
            pass

        # lista de figuras
        fig_list.append(f"{titulo} — {comp_title} vs {title_suffix}")

        # comparação entre tipos, quando existirem grupos irmãos (dppo_/dpio_/dccm_)
        gid = grupo.get("id","")
        if st.session_state.get("cmp_tipos") and gid.startswith(("dppo_","dpio_","dccm_")) and gid != "domicilios_tipo_ocupado":
            base_key = gid.split("_", 1)[1] if "_" in gid else gid
            siblings = [f"dppo_{base_key}", f"dpio_{base_key}", f"dccm_{base_key}"]
            sib_grupos = [g for g in grupos if g.get("id") in siblings]
            if len(sib_grupos) >= 2:
                st.markdown("---")
                st.caption("Comparação por tipo de domicílio (seleção atual)")
                cols = st.columns(len(sib_grupos))
                for ix, g2 in enumerate(sib_grupos):
                    cols2 = [c for c in g2.get("columns", []) if c in df_scope.columns]
                    if not cols2:
                        continue
                    sub = df_scope[cols2].sum(numeric_only=True)
                    df_tmp = pd.DataFrame({"categoria": sub.index, "valor": sub.values})
                    title2 = g2.get("title", "Indicador")
                    df_tmp = _apply_simplify_and_wrap(df_tmp, title2, width=18)
                    with cols[ix]:
                        st.markdown(
                            f"<div class='abnt-figure'><div class='abnt-caption'><strong>{title2}</strong></div></div>",
                            unsafe_allow_html=True,
                        )
                        if g2.get("chart","bar") == "pie" and len(df_tmp) <= 8:
                            f3 = construir_grafico_pizza(df_tmp, categoria_col="categoria_wrapped", titulo=None)
                            if palette:
                                cols_apply3 = colors[:len(df_tmp)]
                                f3.update_traces(marker=dict(colors=cols_apply3))
                        else:
                            f3 = construir_grafico_barra(df_tmp, categoria_col="categoria_wrapped", titulo=None)
                            if palette:
                                cols_apply3 = colors[:len(df_tmp)]
                                f3.update_traces(marker=dict(color=cols_apply3))
                        f3.update_layout(height=360, margin=dict(l=160, r=10, t=10, b=10))
                        f3.update_yaxes(automargin=True)
                        if g2.get("chart","bar") == "pie":
                            f3.update_traces(textposition='outside')
                        st.plotly_chart(f3, use_container_width=True, key=f"dom_{grupo.get('id', titulo)}_sib_{ix}")
                        st.caption("Fonte: Elaboração própria com dados do Censo Demográfico 2022 (IBGE).")
                        # download
                        fname3 = f"{title2.replace(' ', '_')}.csv".replace('—','_').replace('–','-')
                        dataframe_to_csv_download(
                            df_tmp,
                            file_name=fname3,
                            label="Baixar CSV",
                            rename={"categoria_simplificada":"Categoria","valor":"Valor"},
                            columns=["Categoria","Valor"],
                        )
                fig_list.append(f"Comparação por tipo — {titulo} ({title_suffix})")

st.markdown("---")
st.markdown("**Lista de Figuras**")
for i, t in enumerate(fig_list, start=1):
    st.markdown(f"{i}. {t}")
st.caption("Fonte: Censo 2022 — IBGE")
