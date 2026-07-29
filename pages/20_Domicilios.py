import sys
import itertools
import streamlit as st
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for _p in (str(SRC), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from config.config_loader import get_settings
from censo_app.transform import carregar_sp_idade_sexo_enriquecido as carregar_base
from censo_app.viz import construir_grafico_pizza, construir_grafico_barra
from censo_app.ui import render_topbar

st.set_page_config(page_title="Domicílios", layout="wide", initial_sidebar_state="collapsed")
render_topbar(title="Explorador de Dados Censitários", subtitle="Censo 2022 — SP")

SETTINGS = get_settings()

@st.cache_data(show_spinner=True, ttl=3600)
def carregar_df():
    parquet = (SETTINGS.get("paths", {}).get("parquet_default", "data/censo2022_sp.parquet")
               .strip().strip('"').strip("'").replace("\\", "/"))
    excel_rm = (SETTINGS.get("paths", {}).get("rm_au_excel_default", "insumos/Composicao_RM_2024.xlsx")
                .strip().strip('"').strip("'").replace("\\", "/"))
    df = carregar_base(parquet, limite=None, detalhar=False, uf="35", caminho_excel=excel_rm)
    return df

@st.cache_data(show_spinner=False)
def ler_grupos():
    import yaml
    p = Path("config/categorias.yaml")
    with p.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg

def _fmt_mun(cd: str | None, lookup: pd.DataFrame):
    if not cd:
        return "(selecione)"
    row = lookup.loc[lookup["CD_MUN"].astype(str) == str(cd)]
    if row.empty:
        return str(cd)
    return f"{row.iloc[0]['NM_MUN']} ({row.iloc[0]['CD_MUN']})"


# Reutiliza dados já carregados na sessão (Demographics), se disponíveis
if "df_wide_demog" in st.session_state:
    df = st.session_state["df_wide_demog"]
else:
    try:
        with st.spinner("Carregando dados de Domicílios…"):
            df = carregar_df()
        st.session_state["df_wide_demog"] = df
    except Exception as exc:
        st.error(f"❌ Erro ao carregar dados: {exc}")
        st.info("Configure os caminhos em `config/settings.yaml`.")
        st.stop()

_cfg = ler_grupos() or {}
grupos = (_cfg.get("groups") or [])
palette = (_cfg.get("palette") or [])

st.title("🏠 Domicílios — Indicadores Categóricos")

with st.sidebar:
    st.subheader("Filtros")
    sit_opts = sorted(df.get("SITUACAO", pd.Series(dtype=str)).dropna().unique().tolist()) or ["Urbana", "Rural"]
    tipos = sorted(pd.to_numeric(df.get("CD_TIPO"), errors="coerce").dropna().unique().astype(int).tolist())
    sel_sit = st.multiselect("Situação", options=sit_opts, default=sit_opts)
    sel_tipos = st.multiselect("Tipo de Setor", options=tipos, default=tipos)
    nivel = st.selectbox("Nível", ["Estado", "RM/AU", "Região Intermediária", "Região Imediata", "Município", "Setores"], index=0)

df_filt = df.copy()
if "SITUACAO" in df_filt.columns:
    df_filt = df_filt[df_filt["SITUACAO"].isin(sel_sit)]
if "CD_TIPO" in df_filt.columns and sel_tipos:
    df_filt = df_filt[df_filt["CD_TIPO"].isin(sel_tipos)]

# Escopo geográfico
title_suffix = "Estado de São Paulo"
df_scope = df_filt  # default: Estado completo

if nivel == "RM/AU":
    _nome_col = "NOME_RM_AU" if "NOME_RM_AU" in df_filt.columns else ("RM_NOME" if "RM_NOME" in df_filt.columns else None)
    if _nome_col:
        nomes = sorted(df_filt[_nome_col].dropna().unique().tolist())
        sel = st.selectbox("Região (RM/AU)", nomes, key="dom_rmau")
        df_scope = df_filt[df_filt[_nome_col].eq(sel)]
        title_suffix = sel
    else:
        st.warning("Colunas RM/AU não disponíveis nos dados.")
elif nivel == "Região Intermediária" and "NM_RGINT" in df_filt.columns:
    nomes = sorted(df_filt["NM_RGINT"].dropna().unique().tolist())
    sel = st.selectbox("Região Intermediária", nomes, key="dom_rgint")
    df_scope = df_filt[df_filt["NM_RGINT"].eq(sel)]
    title_suffix = sel
elif nivel == "Região Imediata" and "NM_RGI" in df_filt.columns:
    nomes = sorted(df_filt["NM_RGI"].dropna().unique().tolist())
    sel = st.selectbox("Região Imediata", nomes, key="dom_rgi")
    df_scope = df_filt[df_filt["NM_RGI"].eq(sel)]
    title_suffix = sel
elif nivel == "Município" and {"CD_MUN", "NM_MUN"} <= set(df_filt.columns):
    mun_df = df_filt[["CD_MUN", "NM_MUN"]].dropna().drop_duplicates()
    sel_mun = st.selectbox("Município", [None] + mun_df["CD_MUN"].tolist(),
                           format_func=lambda x: _fmt_mun(x, mun_df), key="dom_mun")
    if sel_mun:
        df_scope = df_filt[df_filt["CD_MUN"].astype(str).eq(str(sel_mun))]
        title_suffix = _fmt_mun(sel_mun, mun_df)
    else:
        st.stop()
elif nivel == "Setores" and "CD_SETOR" in df_filt.columns:
    set_opts = sorted(df_filt["CD_SETOR"].dropna().unique().tolist())
    sel_set = st.selectbox("Setor", set_opts, key="dom_setor")
    df_scope = df_filt[df_filt["CD_SETOR"].eq(sel_set)]
    title_suffix = f"Setor {sel_set}"

# ---------------------------------------------------------------------------
# Determinação automática do comparador
# ---------------------------------------------------------------------------
def _determinar_df_comparador(df_scope: pd.DataFrame, df_filt: pd.DataFrame) -> tuple:
    """Retorna (df_comp, label_comp).
    Prioridade: NOME_RM_AU → RM_NOME/AU_NOME → NM_RGI → Estado.
    """
    try:
        if "NOME_RM_AU" in df_scope.columns and df_scope["NOME_RM_AU"].notna().any():
            n = str(df_scope["NOME_RM_AU"].dropna().unique()[0])
            return df_filt[df_filt["NOME_RM_AU"] == n], f"RM/AU — {n}"
        if "RM_NOME" in df_scope.columns and df_scope["RM_NOME"].notna().any():
            n = str(df_scope["RM_NOME"].dropna().unique()[0])
            return df_filt[df_filt["RM_NOME"] == n], f"RM — {n}"
        if "AU_NOME" in df_scope.columns and df_scope["AU_NOME"].notna().any():
            n = str(df_scope["AU_NOME"].dropna().unique()[0])
            return df_filt[df_filt["AU_NOME"] == n], f"AU — {n}"
        if "NM_RGI" in df_scope.columns and df_scope["NM_RGI"].notna().any():
            rgi = str(df_scope["NM_RGI"].dropna().unique()[0])
            return df_filt[df_filt["NM_RGI"] == rgi], f"Reg. Imediata — {rgi}"
    except Exception:
        pass
    return df_filt, "Estado de São Paulo"


# Para escopos menores que Estado, determine comparador automático
if nivel in ("Município", "Setores", "RM/AU", "Região Imediata", "Região Intermediária") and nivel != "Estado":
    df_comp, comp_label = _determinar_df_comparador(df_scope, df_filt)
    # Se comparador == escopo (mesma RM/AU selecionada), sobe para Estado
    if df_comp is df_scope or (df_comp is not None and len(df_comp) == len(df_scope)):
        df_comp, comp_label = df_filt, "Estado de São Paulo"
else:
    # Estado: sem comparador (coluna da esquerda fica vazia ou mostra SP inteiro)
    df_comp, comp_label = df_filt, "Estado de São Paulo"
    # Para nível Estado, não há diferença entre scope e comp, então só mostra uma coluna
    if nivel == "Estado":
        df_comp = pd.DataFrame()  # sem comparador no nível Estado

# ---------------------------------------------------------------------------
# Cabeçalho das colunas
# ---------------------------------------------------------------------------
col_esq, col_dir = st.columns(2)
with col_esq:
    st.caption(f"📊 Comparador: **{comp_label}** (%)" if not df_comp.empty else "📊 Estado de SP (%)")
with col_dir:
    st.caption(f"📌 Selecionado: **{title_suffix}** (absoluto)")

for grupo in grupos:
    cols = [c for c in grupo.get("columns", []) if c in df_scope.columns]
    if not cols:
        continue
    titulo = grupo.get("title", "Indicador")
    chart = grupo.get("chart", "bar")

    def _build(df_in: pd.DataFrame) -> pd.DataFrame:
        sub = df_in[cols].copy()
        vals = sub.sum(numeric_only=True)
        out = pd.DataFrame({"categoria": vals.index, "valor": vals.values})
        out = out[out["valor"].notna() & (out["valor"] > 0)]
        return out

    base_comp = _build(df_comp) if not df_comp.empty else pd.DataFrame(columns=["categoria", "valor"])
    base_sel = _build(df_scope)

    if palette:
        n_colors = max(len(base_comp), len(base_sel), 1)
        colors = list(itertools.islice(itertools.cycle(palette), n_colors))

    with st.container():
        st.subheader(titulo)
        c1, c2 = st.columns(2)
        with c1:
            if not base_comp.empty:
                if chart == "pie" and len(base_comp) <= 8:
                    fig = construir_grafico_pizza(base_comp, titulo=f"{titulo} — {comp_label} (%)")
                else:
                    fig = construir_grafico_barra(base_comp, titulo=f"{titulo} — {comp_label} (%)")
                if palette:
                    fig.update_traces(marker=dict(colorscale=None), marker_colors=colors[:len(base_comp)])
                st.plotly_chart(fig, use_container_width=True)
                st.caption("Fonte: Elaboração própria com dados do Censo Demográfico 2022 (IBGE).")
            elif nivel == "Estado":
                st.info("Sem comparador disponível para o nível Estado.")
        with c2:
            if not base_sel.empty:
                if chart == "pie" and len(base_sel) <= 8:
                    fig2 = construir_grafico_pizza(base_sel, titulo=f"{titulo} — {title_suffix}")
                else:
                    fig2 = construir_grafico_barra(base_sel, titulo=f"{titulo} — {title_suffix}")
                if palette:
                    fig2.update_traces(marker=dict(colorscale=None), marker_colors=colors[:len(base_sel)])
                st.plotly_chart(fig2, use_container_width=True)
                st.caption("Fonte: Elaboração própria com dados do Censo Demográfico 2022 (IBGE).")

st.caption("Fonte: Censo 2022 — IBGE")
