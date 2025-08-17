import sys
from pathlib import Path as _P
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

# importar módulos centrais
ROOT = _P(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from censo_app.transform import (
    carregar_sp_idade_sexo_enriquecido, largura_para_longo_piramide,
)
from censo_app.viz import construir_piramide_etaria as _construir_piramide
from censo_app.ui import renderizar_barra_superior as _renderizar_barra_superior
from censo_app.ui_utils import ensure_abnt_css, dataframe_to_csv_download
from config.config_loader import get_settings, get_page_config
from censo_app.demog_utils import (
    normalize_age_label as _normalize_age_label,
    pad_pyramid_categories as _pad_cats_util,
    aggregate_sex_age as _aggregate_local,
)
from censo_app.formatting import fmt_br as _fmt_br
try:
    from censo_app.text_utils import (
        sanitize_title as _sanitize_title_shared,
        clean_label as _clean_label_shared,
        wrap_title as _wrap_title_shared,
    )
except ModuleNotFoundError:
    # Fallback: reforça caminhos e tenta importação direta por arquivo
    try:
        PKG = SRC / "censo_app"
        for pth in (str(SRC), str(ROOT), str(PKG)):
            if pth not in sys.path:
                sys.path.insert(0, pth)
        from censo_app.text_utils import (
            sanitize_title as _sanitize_title_shared,
            clean_label as _clean_label_shared,
            wrap_title as _wrap_title_shared,
        )
    except Exception:
        import importlib.util as _ilu
        _fp = (SRC / "censo_app" / "text_utils.py").resolve()
        spec = _ilu.spec_from_file_location("censo_app.text_utils", str(_fp))
        mod = _ilu.module_from_spec(spec)  # type: ignore[arg-type]
        assert spec and spec.loader
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        _sanitize_title_shared = mod.sanitize_title
        _clean_label_shared = mod.clean_label
        _wrap_title_shared = mod.wrap_title
from censo_app.tables import build_abnt_demographic_table as _build_abnt_table, render_abnt_html as _render_abnt_html

# Mapeamentos simplificados para os filtros (agora vindos do YAML quando disponível)
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
# SITUACAO_DET_MAP não utilizado nesta página

# usa _aggregate_local importado de demog_utils

DEMOG_CFG = get_page_config('demografia')
# Carrega TIPO_MAP do YAML se existir
TIPO_MAP = _TIPO_MAP_DEFAULT
try:
    cfg_types = DEMOG_CFG.get('sector_types', None)
    if isinstance(cfg_types, dict) and cfg_types:
        # Chaves no YAML podem vir como strings
        TIPO_MAP = {int(k): str(v) for k, v in cfg_types.items()}
except Exception:
    pass

def _pad_pyramid_categories(df: pd.DataFrame) -> pd.DataFrame:
    try:
        faixas_ordem = DEMOG_CFG.get('age_buckets_order', [
            "0 a 4 anos", "5 a 9 anos", "10 a 14 anos", "15 a 19 anos",
            "20 a 24 anos", "25 a 29 anos", "30 a 39 anos", "40 a 49 anos",
            "50 a 59 anos", "60 a 69 anos", "70 anos ou mais"
        ])
        return _pad_cats_util(df, faixas_ordem)
    except Exception:
        return df

# _fmt_br já foi importado de censo_app.formatting

_normalize_age_label = _normalize_age_label

def _sanitize_title(title: str | None) -> str:
    return _sanitize_title_shared(title)

def create_abnt_demographic_table(df_plot, title_suffix=""):
    faixas_ordem = DEMOG_CFG.get('age_buckets_order', [
        "0 a 4 anos", "5 a 9 anos", "10 a 14 anos", "15 a 19 anos",
        "20 a 24 anos", "25 a 29 anos", "30 a 39 anos", "40 a 49 anos",
        "50 a 59 anos", "60 a 69 anos", "70 anos ou mais"
    ])
    return _build_abnt_table(df_plot, faixas_ordem)

# RM/AU agora são enriquecidas no transform.py a partir do Excel diretamente

# Removido helper local make_age_pyramid (não utilizado; usamos censo_app.viz.make_age_pyramid)

UI_CFG = get_page_config('demografia_ui') or {}
st.set_page_config(layout="wide", initial_sidebar_state=UI_CFG.get('layout', {}).get('initial_sidebar_state', 'collapsed'))
tb = UI_CFG.get('topbar', {})
_renderizar_barra_superior(titulo=tb.get('title', "Explorador de Dados Censitários"), subtitulo=tb.get('subtitle', "Censo 2022 — SP"))
st.title(UI_CFG.get('title', "Demografia"))

# CSS: destacar selects como "botões" e permitir quebras em labels/títulos
st.markdown(
    """
    <style>
    /* Reduzir margens laterais para ganhar largura útil */
    .block-container {
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
        max-width: 100% !important;
    }
    /* Diminuir espaçamento entre colunas */
    div[data-testid="stHorizontalBlock"] { gap: 0.5rem !important; }
    div[data-testid="column"] { padding-left: 0.25rem !important; padding-right: 0.25rem !important; }
    /* Aparência mais chamativa nos selects/multiselects */
    div[data-baseweb="select"] > div {
        background-color: #e0eeff !important; /* mais vivo que o padrão */
        border: 2px solid #0b61f1 !important;
        border-radius: 10px !important;
        box-shadow: inset 0 1px 0 rgba(11,97,241,0.18) !important;
        transition: box-shadow .15s ease-in-out, border-color .15s ease-in-out;
    }
    div[data-baseweb="select"] > div:hover {
        box-shadow: 0 0 0 3px rgba(11,97,241,0.28) !important;
        border-color: #094ec4 !important;
    }
    /* Permitir quebra de linha em labels/valores de selects */
    .stSelectbox label, .stMultiSelect label { white-space: normal !important; }
    div[data-baseweb="select"] [role="combobox"] { white-space: normal !important; }
    div[data-baseweb="select"] span { white-space: normal !important; }
    /* Títulos/subtítulos com quebra quando longos */
    .block-container h1, .block-container h2, .block-container h3, .block-container h4 {
        white-space: normal !important;
        overflow-wrap: anywhere;
        word-break: break-word;
    }
    /* ABNT: wrapper e legendas padronizadas para gráficos */
    .abnt-figure { max-width: 16cm; margin: 0.25rem auto 0.25rem auto; }
    .abnt-caption { text-align: center; font-weight: 700; font-size: 11pt; line-height: 1.2; height: 48px; overflow: hidden; display: flex; align-items: center; justify-content: center; }
    .abnt-source { font-size: 10pt; text-align: left; margin-top: 6px; }
    /* Limitar e centralizar gráficos Plotly para até 16cm */
    .stPlotlyChart { max-width: 16cm; margin-left: auto; margin-right: auto; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Garantir CSS ABNT padronizado (legendas e fontes de figuras) após CSS da página
ensure_abnt_css()

# Página enxuta: sem controles internos desnecessários no sidebar

def _norm(s: str) -> str:
    return (s or "").strip().strip('"').strip("'").replace("\\", "/")

def _wrap_title(texto: str, width: int = 42) -> str:
    return _wrap_title_shared(texto, width)

settings = get_settings()
parquet_path = _norm(settings.get('paths', {}).get('parquet_default', r"D:\\repo\\saida_parquet\\base_integrada_final.parquet"))
rm_xlsx_path = _norm(settings.get('paths', {}).get('rm_au_excel_default', r"D:\\repo\\insumos\\Composicao_RM_2024.xlsx"))

@st.cache_data(show_spinner=True, ttl=3600)
def _load_data(parquet_path: str, limit: int | None = None, excel_rm_au: str | None = None):
    # excel_rm_au é passado para o transform, que fará o merge RM/AU
    df = carregar_sp_idade_sexo_enriquecido(parquet_path, limite=limit, detalhar=False, uf="35", caminho_excel=excel_rm_au)
    return df

def _generate_rm_au_csv_from_excel(excel_path: str, csv_path: str) -> bool:
    """Gera CSV (CD_MUN, RM_NOME, AU_NOME) a partir do Excel com abas RM e AU.
    Retorna True se conseguiu salvar, False caso contrário.
    """
    try:
        xl = pd.ExcelFile(excel_path)
        sheet_names = {s.lower(): s for s in xl.sheet_names}
        rm_sheet = sheet_names.get("rm")
        au_sheet = sheet_names.get("au")
        if not (rm_sheet or au_sheet):
            return False
        def _detect_cols(df: pd.DataFrame, is_rm: bool):
            cols = {c.lower(): c for c in df.columns}
            code_keys = [
                "cd_mun","codigo_municipio","codigo_ibge","cod_mun","cd_municipio",
                "cod_municipio","cod_ibge","ibge","cd_geocodm","cd_mun_7","cd_mun_6"
            ]
            name_keys_rm = ["rm_nome","nome_rm","rm","regiao_metropolitana","nome_regiao_metropolitana"]
            name_keys_au = ["au_nome","nome_au","au","aglomeracao_urbana","nome_aglomeracao_urbana"]
            code_col = next((cols[k] for k in code_keys if k in cols), None)
            name_col = next((cols[k] for k in (name_keys_rm if is_rm else name_keys_au) if k in cols), None)
            return code_col, name_col
        rm_map = pd.DataFrame(columns=["CD_MUN","RM_NOME"]) ; au_map = pd.DataFrame(columns=["CD_MUN","AU_NOME"])    
        if rm_sheet:
            df_rm = xl.parse(rm_sheet)
            code_col, name_col = _detect_cols(df_rm, is_rm=True)
            if code_col and name_col:
                tmp = df_rm[[code_col, name_col]].copy()
                tmp["CD_MUN"] = pd.Series(tmp[code_col]).astype(str).str.replace(r"\D", "", regex=True).str.zfill(7)
                rm_map = tmp[["CD_MUN", name_col]].rename(columns={name_col: "RM_NOME"}).drop_duplicates()
        if au_sheet:
            df_au = xl.parse(au_sheet)
            code_col, name_col = _detect_cols(df_au, is_rm=False)
            if code_col and name_col:
                tmp = df_au[[code_col, name_col]].copy()
                tmp["CD_MUN"] = pd.Series(tmp[code_col]).astype(str).str.replace(r"\D", "", regex=True).str.zfill(7)
                au_map = tmp[["CD_MUN", name_col]].rename(columns={name_col: "AU_NOME"}).drop_duplicates()
        out = rm_map.merge(au_map, on="CD_MUN", how="outer")
        if out.empty:
            return False
        _P(csv_path).parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(csv_path, index=False)
        return True
    except Exception:
        return False

def _ensure_rm_au_csv(df_wide: pd.DataFrame, csv_path: str, excel_paths: list[str] | None = None) -> str:
    """Garante a existência do CSV. Tenta Excel (lista de caminhos) primeiro; se falhar, cai para wide."""
    p = _P(csv_path)
    try:
        if p.exists():
            return str(p)
        # Tentar gerar via Excel (preferencial)
        for xp in (excel_paths or []):
            if xp and _P(xp).exists():
                if _generate_rm_au_csv_from_excel(xp, str(p)):
                    # Enriquecer com NM_MUN se possível
                    try:
                        if "NM_MUN" in df_wide.columns:
                            base = pd.read_csv(p)
                            nm = df_wide[["CD_MUN","NM_MUN"]].dropna().copy()
                            nm["CD_MUN"] = nm["CD_MUN"].astype(str).str.strip()
                            base["CD_MUN"] = base["CD_MUN"].astype(str).str.strip()
                            base = base.merge(nm.drop_duplicates("CD_MUN"), on="CD_MUN", how="left")
                            # Reordenar
                            cols = [c for c in ["CD_MUN","NM_MUN","RM_NOME","AU_NOME"] if c in base.columns]
                            base[cols].to_csv(p, index=False)
                    except Exception:
                        pass
                    return str(p)
        # Fallback: derivar do wide (se contiver RM/AU)
        p.parent.mkdir(parents=True, exist_ok=True)
        if "CD_MUN" not in df_wide.columns:
            # não temos como gerar; cria esqueleto vazio para não quebrar
            pd.DataFrame({"CD_MUN": []}).to_csv(p, index=False)
            return str(p)
        g = df_wide.copy()
        g["CD_MUN"] = g["CD_MUN"].astype(str).str.strip()
        cols = ["CD_MUN"] + [c for c in ["RM_NOME","AU_NOME"] if c in g.columns]
        if len(cols) == 1:
            pd.DataFrame({"CD_MUN": g["CD_MUN"].drop_duplicates()}).to_csv(p, index=False)
            return str(p)
        map_df = g[cols].dropna(how="all").drop_duplicates()
        map_df = map_df.groupby("CD_MUN", as_index=False).agg({c:"first" for c in cols if c!="CD_MUN"})
        # Enriquecer com NM_MUN se possível
        if "NM_MUN" in g.columns:
            nm = g[["CD_MUN","NM_MUN"]].dropna().drop_duplicates("CD_MUN")
            map_df = map_df.merge(nm, on="CD_MUN", how="left")
            # Reordenar preferindo NM_MUN após CD_MUN
            order = [c for c in ["CD_MUN","NM_MUN","RM_NOME","AU_NOME"] if c in map_df.columns]
            map_df = map_df[order]
        map_df.to_csv(p, index=False)
        return str(p)
    except Exception:
        return str(p)

if "df_wide_demog" not in st.session_state:
    if hasattr(st, "status"):
        with st.status("Carregando dados de Demografia…", expanded=True) as st_status:
            prog = st.progress(0, text="Preparando…")
            prog.progress(15, text="Validando caminhos…")
            prog.progress(35, text="Lendo e enriquecendo…")
            try:
                df_wide = _load_data(parquet_path, None, rm_xlsx_path)
                st.session_state["df_wide_demog"] = df_wide
                prog.progress(90, text="Finalizando…")
                st_status.update(label="Dados carregados", state="complete")
                prog.progress(100)
            except Exception as e:
                st_status.update(label=f"Erro: {e}", state="error")
                st.error(f"❌ Erro ao carregar: {e}")
                st.stop()
    else:
        try:
            with st.spinner("Carregando dados de Demografia…"):
                df_wide = _load_data(parquet_path, None, rm_xlsx_path)
                st.session_state["df_wide_demog"] = df_wide
        except Exception as e:
            st.error(f"❌ Erro ao carregar: {e}")
            st.stop()
else:
    df_wide = st.session_state["df_wide_demog"]
    # silencioso para usuário final

# Conversão para formato long para análise, com barra de progresso
try:
    if hasattr(st, "status"):
        with st.status("Preparando dados…", expanded=False) as st_status:
            prog = st.progress(0, text="Convertendo para formato longo…")
            df_long_full = largura_para_longo_piramide(df_wide)
            prog.progress(60, text="Renomeando colunas…")
            df_long = df_long_full.rename(columns={"idade_grupo": "faixa_etaria", "valor": "populacao"})
            if "faixa_etaria" in df_long.columns:
                df_long["faixa_etaria"] = df_long["faixa_etaria"].apply(_normalize_age_label)
            prog.progress(100)
            st_status.update(label="Dados prontos", state="complete")
    else:
        with st.spinner("Preparando dados…"):
            df_long_full = largura_para_longo_piramide(df_wide)
            df_long = df_long_full.rename(columns={"idade_grupo": "faixa_etaria", "valor": "populacao"})
            if "faixa_etaria" in df_long.columns:
                df_long["faixa_etaria"] = df_long["faixa_etaria"].apply(_normalize_age_label)
    # silencioso
except Exception as e:
    st.error(f"❌ Erro na conversão para formato long: {e}")
    st.stop()

# Sanitização ampla de rótulos para remover 'undefined'/vazios antes dos filtros
def _clean_label(val: object) -> object:
    v = _clean_label_shared(val)
    return pd.NA if v is None else v

for _col in ["NOME_RM_AU", "TIPO_RM_AU", "RM_NOME", "AU_NOME", "NM_MUN", "NM_RGI", "NM_RGINT", "faixa_etaria"]:
    if _col in df_long.columns:
        df_long[_col] = df_long[_col].apply(_clean_label)

# Sem diagnósticos internos

st.divider()
st.subheader(UI_CFG.get('labels', {}).get('filters_title', "🔍 Filtros Básicos"))

# Layout de filtros em colunas
c1, c2, c3 = st.columns(3)

# Filtro 1: Situação Urbana/Rural (padrão: Urbana)
with c1:
    if "SITUACAO" in df_long.columns:
        sit_opts = sorted([x for x in df_long["SITUACAO"].dropna().unique() if x in ("Urbana", "Rural")])
    else:
        sit_opts = []
    # Default: selecionar todas as situações disponíveis (Urbana e Rural) quando existir
    default_sit = sit_opts if sit_opts else UI_CFG.get('defaults', {}).get('situacao', ["Urbana","Rural"])  # via YAML se desejar
    sel_situacao = st.multiselect(UI_CFG.get('filters', {}).get('situacao_label', "Situação"), sit_opts, default=default_sit, key="fil_situacao_demog")
    if sel_situacao:
        df_long = df_long[df_long["SITUACAO"].isin(sel_situacao)]

# Filtro 2: Tipo de Setor (padrão: 0 e 1)
with c2:
    if "CD_TIPO" in df_long.columns:
        # Mostrar sempre os 10 tipos previstos
        tipo_opts = [(k, TIPO_MAP.get(k, str(k))) for k in sorted(TIPO_MAP.keys())]
        # Default: selecionar todos os tipos
        default_items = tipo_opts
        sel_tipo = st.multiselect(
            UI_CFG.get('filters', {}).get('tipo_setor_label', "Tipo de Setor"),
            tipo_opts,
            default=default_items,
            format_func=lambda x: f"{x[0]} — {x[1]}",
            key="fil_tipo_demog",
        )
        if sel_tipo:
            df_long = df_long[df_long["CD_TIPO"].isin([k for k, _ in sel_tipo])]

# Filtro 3: RM/AU (se disponível)
with c3:
    # Preferir colunas unificadas
    if "NOME_RM_AU" in df_long.columns and "TIPO_RM_AU" in df_long.columns:
        _opts = (
            df_long[["TIPO_RM_AU","NOME_RM_AU"]]
            .dropna()
            .assign(TIPO_RM_AU=lambda d: d["TIPO_RM_AU"].astype(str).str.upper())
            .drop_duplicates()
            .sort_values(["TIPO_RM_AU","NOME_RM_AU"])  # type: ignore
        )
        options = [f"{t} — {n}" for t, n in _opts.itertuples(index=False, name=None)]
        options = ["Todas"] + options
        sel_pairs = st.multiselect(UI_CFG.get('filters', {}).get('rm_au_label', "RM/AU"), options, default=["Todas"], key="fil_rm_au_demog")
        if "Todas" not in sel_pairs and sel_pairs:
            mask = pd.Series([False] * len(df_long))
            for s in sel_pairs:
                try:
                    tipo, nome = s.split(" — ", 1)
                except ValueError:
                    continue
                mask |= (df_long["TIPO_RM_AU"].astype(str).str.upper() == tipo.upper()) & (df_long["NOME_RM_AU"] == nome)
            df_long = df_long[mask]
    else:
        rm_au_options = []
        if "RM_NOME" in df_long.columns:
            _rms = pd.Series(df_long["RM_NOME"]).dropna().astype(str)
            _rms = _rms[~_rms.str.strip().str.lower().isin(["undefined","nan","none","null",""])]
            rms = [f"RM: {x}" for x in sorted(_rms.unique())]
            rm_au_options.extend(rms)
        if "AU_NOME" in df_long.columns:
            _aus = pd.Series(df_long["AU_NOME"]).dropna().astype(str)
            _aus = _aus[~_aus.str.strip().str.lower().isin(["undefined","nan","none","null",""])]
            aus = [f"AU: {x}" for x in sorted(_aus.unique())]
            rm_au_options.extend(aus)
        if rm_au_options:
            sel_rm_au_filter = st.multiselect(UI_CFG.get('filters', {}).get('rm_au_label', "RM/AU"), ["Todas"] + rm_au_options,
                                              default=["Todas"], key="fil_rm_au_demog")
            if "Todas" not in sel_rm_au_filter and sel_rm_au_filter:
                cond = pd.Series([False] * len(df_long))
                for sel in sel_rm_au_filter:
                    if sel.startswith("RM: "):
                        rm_name = sel[4:]
                        cond |= (df_long["RM_NOME"] == rm_name)
                    elif sel.startswith("AU: "):
                        au_name = sel[4:]
                        cond |= (df_long["AU_NOME"] == au_name)
                df_long = df_long[cond]

st.write(f"{UI_CFG.get('labels', {}).get('filtered_count_prefix', '**Dados filtrados:**')} {len(df_long):,} registros")

st.divider()
st.subheader(UI_CFG.get('labels', {}).get('analysis_title', "📊 Análise Demográfica"))

# Helpers para opções
def _mk_municipios(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["CD_MUN","NM_MUN"]
    return df[cols].dropna().drop_duplicates().sort_values(["NM_MUN","CD_MUN"]) if all(c in df.columns for c in cols) else pd.DataFrame(columns=cols)

def _mk_rm_au_options(df: pd.DataFrame) -> pd.DataFrame:
    """Constrói opções limpas de RM/AU, sem rótulos vazios/undefined."""
    if {"TIPO_RM_AU", "NOME_RM_AU"}.issubset(df.columns):
        out = df[["TIPO_RM_AU", "NOME_RM_AU"]].copy()
        out["TIPO_RM_AU"] = out["TIPO_RM_AU"].apply(_clean_label).astype(str).str.upper()
        out["NOME_RM_AU"] = out["NOME_RM_AU"].apply(_clean_label)
        out = out.dropna().drop_duplicates().sort_values(["TIPO_RM_AU", "NOME_RM_AU"]).reset_index(drop=True)  # type: ignore
        out["LABEL"] = out["TIPO_RM_AU"] + " — " + out["NOME_RM_AU"].astype(str)
        return out
    frames = []
    if "RM_NOME" in df.columns:
        a = df[["RM_NOME"]].copy()
        a["RM_NOME"] = a["RM_NOME"].apply(_clean_label)
        a = a.dropna().drop_duplicates().rename(columns={"RM_NOME": "NOME"})
        a["TIPO"] = "RM"
        frames.append(a)
    if "AU_NOME" in df.columns:
        b = df[["AU_NOME"]].copy()
        b["AU_NOME"] = b["AU_NOME"].apply(_clean_label)
        b = b.dropna().drop_duplicates().rename(columns={"AU_NOME": "NOME"})
        b["TIPO"] = "AU"
        frames.append(b)
    if not frames:
        return pd.DataFrame(columns=["TIPO_RM_AU", "NOME_RM_AU", "LABEL"])
    c = pd.concat(frames, ignore_index=True)
    c = c.dropna().drop_duplicates().sort_values(["TIPO", "NOME"]).reset_index(drop=True)
    c = c.rename(columns={"TIPO": "TIPO_RM_AU", "NOME": "NOME_RM_AU"})
    c["LABEL"] = c["TIPO_RM_AU"] + " — " + c["NOME_RM_AU"].astype(str)
    return c

# Escala de análise em ordem: Estado, RM/AU, Região Intermediária, Região Imediata, Município, Setores
scale_options = ["Estado"]
has_rm_au = {"TIPO_RM_AU","NOME_RM_AU"}.issubset(df_long.columns) or any(c in df_long.columns for c in ["RM_NOME","AU_NOME"]) 
has_rgint = "NM_RGINT" in df_long.columns and df_long["NM_RGINT"].notna().any()
has_rgi = "NM_RGI" in df_long.columns and df_long["NM_RGI"].notna().any()
has_mun = all(c in df_long.columns for c in ["CD_MUN","NM_MUN"])
has_setor = has_mun and ("CD_SETOR" in df_long.columns)
if has_rm_au: scale_options.append("RM/AU")
if has_rgint: scale_options.append("Região Intermediária")
if has_rgi: scale_options.append("Região Imediata")
if has_mun: scale_options.append("Município")
if has_setor: scale_options.append("Setores")
nivel = st.selectbox(UI_CFG.get('filters', {}).get('escala_label', "Escala de Análise"), options=scale_options, index=0, key="nivel_demog")

# Seleção por escala
comp_available = False  # controla se há comparador válido para o layout

# Inicializa comparador da execução atual
df_comp_plot = None
comp_title = None

# Seleção por escala
if nivel == "Estado":
    df_analysis = df_long
    title_suffix = "Estado de São Paulo"

elif nivel == "RM/AU" and has_rm_au:
    rmau_df = _mk_rm_au_options(df_long)
    if rmau_df.empty:
        st.error("❌ Nenhuma RM/AU disponível nos dados filtrados")
        st.stop()
    sel = st.selectbox(UI_CFG.get('labels', {}).get('select_region_rmau', "Região (RM/AU) — selecione ou digite"), options=rmau_df.index.tolist(), format_func=lambda i: rmau_df.loc[i, "LABEL"], key="sel_rmau_analysis")
    rec = rmau_df.loc[sel]
    if {"TIPO_RM_AU","NOME_RM_AU"}.issubset(df_long.columns):
        mask = (df_long["TIPO_RM_AU"].astype(str).str.upper()==str(rec["TIPO_RM_AU"]).upper()) & (df_long["NOME_RM_AU"]==rec["NOME_RM_AU"])    
        df_analysis = df_long[mask]
    else:
        if str(rec["TIPO_RM_AU"]).upper()=="RM" and "RM_NOME" in df_long.columns:
            df_analysis = df_long[df_long["RM_NOME"]==rec["NOME_RM_AU"]]
        elif str(rec["TIPO_RM_AU"]).upper()=="AU" and "AU_NOME" in df_long.columns:
            df_analysis = df_long[df_long["AU_NOME"]==rec["NOME_RM_AU"]]
        else:
            df_analysis = df_long.head(0)
    title_suffix = rec["LABEL"]

elif nivel == "Região Intermediária" and has_rgint:
    rgints = sorted([x for x in df_long["NM_RGINT"].dropna().unique().tolist()])
    sel_rgint = st.selectbox(UI_CFG.get('labels', {}).get('select_region_rgint', "Região Intermediária — selecione ou digite"), rgints, key="sel_rgint_analysis")
    df_analysis = df_long[df_long["NM_RGINT"]==sel_rgint]
    title_suffix = f"Região Intermediária — {sel_rgint}"

elif nivel == "Região Imediata" and has_rgi:
    rgis = sorted([x for x in df_long["NM_RGI"].dropna().unique().tolist()])
    sel_rgi = st.selectbox(UI_CFG.get('labels', {}).get('select_region_rgi', "Região Imediata — selecione ou digite"), rgis, key="sel_rgi_analysis")
    df_analysis = df_long[df_long["NM_RGI"]==sel_rgi]
    title_suffix = f"Região Imediata — {sel_rgi}"

elif nivel in ("Município","Setores") and has_mun:
    mun_df = _mk_municipios(df_long)
    if len(mun_df)==0:
        st.error("❌ Nenhum município disponível nos dados filtrados")
        st.stop()
    name_map = dict(zip(mun_df["CD_MUN"], mun_df["NM_MUN"]))
    def _fmt(c):
        if c is None:
            return "— selecione ou digite —"
        val = name_map.get(c, "")
        try:
            import pandas as _pd
            if _pd.isna(val):
                val = ""
        except Exception:
            # Fallback simples caso pandas não esteja disponível
            val = "" if str(val).lower() in ("nan","none","undefined") else val
        return f"{c} — {val}"
    sel_mun = st.selectbox(UI_CFG.get('labels', {}).get('select_municipio', "Município — selecione ou digite"), options=[None]+mun_df["CD_MUN"].tolist(), format_func=_fmt, key="sel_mun_analysis")
    if sel_mun is None:
        st.info("Selecione ou digite um município para continuar.")
        st.stop()
    df_scope = df_long[df_long["CD_MUN"]==sel_mun]
    if nivel == "Município":
        desag = st.checkbox(UI_CFG.get('labels', {}).get('checkbox_desag_mun', "Desagregar por setores do município"), value=False, key="mun_desag_demog")
        if not desag:
            df_analysis = df_scope
            title_suffix = _fmt(sel_mun)
            # Preparar comparador: RM/AU (preferência) ou Região Imediata
            df_comp_plot = None
            comp_title = None
            if hasattr(st, "status"):
                with st.status("Determinando comparador…", expanded=False) as st_status:
                    prog = st.progress(0, text="Identificando região…")
                    try:
                        # Preferência: colunas unificadas RM/AU
                        if {"TIPO_RM_AU","NOME_RM_AU"}.issubset(df_scope.columns) and df_scope[["TIPO_RM_AU","NOME_RM_AU"]].dropna().shape[0] > 0:
                            pair = (df_scope[["TIPO_RM_AU","NOME_RM_AU"]].dropna().drop_duplicates().iloc[0])
                            t, n = str(pair["TIPO_RM_AU"]).upper(), str(pair["NOME_RM_AU"])
                            mask = (df_long["TIPO_RM_AU"].astype(str).str.upper()==t) & (df_long["NOME_RM_AU"]==n)
                            df_comp_base = df_long[mask]
                            comp_title = f"{t} — {n}"
                        else:
                            # Legado: RM_NOME / AU_NOME no município
                            if "RM_NOME" in df_scope.columns and df_scope["RM_NOME"].notna().any():
                                n = str(df_scope["RM_NOME"].dropna().unique()[0])
                                df_comp_base = df_long[df_long["RM_NOME"]==n] if "RM_NOME" in df_long.columns else pd.DataFrame(columns=df_long.columns)
                                comp_title = f"RM — {n}"
                            elif "AU_NOME" in df_scope.columns and df_scope["AU_NOME"].notna().any():
                                n = str(df_scope["AU_NOME"].dropna().unique()[0])
                                df_comp_base = df_long[df_long["AU_NOME"]==n] if "AU_NOME" in df_long.columns else pd.DataFrame(columns=df_long.columns)
                                comp_title = f"AU — {n}"
                            else:
                                # Região Imediata
                                if "NM_RGI" in df_scope.columns and df_scope["NM_RGI"].notna().any():
                                    rgi = str(df_scope["NM_RGI"].dropna().unique()[0])
                                    df_comp_base = df_long[df_long["NM_RGI"]==rgi] if "NM_RGI" in df_long.columns else pd.DataFrame(columns=df_long.columns)
                                    comp_title = f"Região Imediata — {rgi}"
                                else:
                                    df_comp_base = pd.DataFrame(columns=df_long.columns)
                        prog.progress(65, text="Agregando comparador…")
                        if not comp_title:
                            # Último recurso: Estado
                            df_comp_base = df_long
                            comp_title = "Estado de São Paulo"
                        if not df_comp_base.empty:
                            df_comp_plot = _aggregate_local(df_comp_base)
                            comp_available = True
                        comp_title = _sanitize_title(comp_title)
                        prog.progress(100)
                        st_status.update(label=f"Comparador: {comp_title}", state="complete")
                    except Exception:
                        st_status.update(label="Comparador não identificado", state="error")
                        df_comp_plot = None
            else:
                try:
                    if {"TIPO_RM_AU","NOME_RM_AU"}.issubset(df_scope.columns) and df_scope[["TIPO_RM_AU","NOME_RM_AU"]].dropna().shape[0] > 0:
                        pair = (df_scope[["TIPO_RM_AU","NOME_RM_AU"]].dropna().drop_duplicates().iloc[0])
                        t, n = str(pair["TIPO_RM_AU"]).upper(), str(pair["NOME_RM_AU"])
                        mask = (df_long["TIPO_RM_AU"].astype(str).str.upper()==t) & (df_long["NOME_RM_AU"]==n)
                        df_comp_base = df_long[mask]
                        comp_title = f"{t} — {n}"
                    else:
                        if "RM_NOME" in df_scope.columns and df_scope["RM_NOME"].notna().any():
                            n = str(df_scope["RM_NOME"].dropna().unique()[0])
                            df_comp_base = df_long[df_long["RM_NOME"]==n] if "RM_NOME" in df_long.columns else pd.DataFrame(columns=df_long.columns)
                            comp_title = f"RM — {n}"
                        elif "AU_NOME" in df_scope.columns and df_scope["AU_NOME"].notna().any():
                            n = str(df_scope["AU_NOME"].dropna().unique()[0])
                            df_comp_base = df_long[df_long["AU_NOME"]==n] if "AU_NOME" in df_long.columns else pd.DataFrame(columns=df_long.columns)
                            comp_title = f"AU — {n}"
                        else:
                            if "NM_RGI" in df_scope.columns and df_scope["NM_RGI"].notna().any():
                                rgi = str(df_scope["NM_RGI"].dropna().unique()[0])
                                df_comp_base = df_long[df_long["NM_RGI"]==rgi] if "NM_RGI" in df_long.columns else pd.DataFrame(columns=df_long.columns)
                                comp_title = f"Região Imediata — {rgi}"
                            else:
                                df_comp_base = pd.DataFrame(columns=df_long.columns)
                    if not comp_title:
                        df_comp_base = df_long
                        comp_title = "Estado de São Paulo"
                    if not df_comp_base.empty:
                        df_comp_plot = _aggregate_local(df_comp_base)
                        comp_available = True
                    comp_title = _sanitize_title(comp_title)
                except Exception:
                    df_comp_plot = None
                    comp_available = False
        else:
            if not has_setor:
                st.error("❌ Colunas de setor não disponíveis")
                st.stop()
            setor_options = sorted(df_scope["CD_SETOR"].dropna().unique()) if "CD_SETOR" in df_scope.columns else []
            if len(setor_options)==0:
                st.error("❌ Nenhum setor disponível para o município selecionado")
                st.stop()
            sel_setor = st.selectbox(UI_CFG.get('labels', {}).get('select_setor_mun', "Setor do Município — selecione ou digite"), options=setor_options, key="sel_setor_mun_analysis")
            df_analysis = df_scope[df_scope["CD_SETOR"]==sel_setor]
            title_suffix = f"Setor {sel_setor} — {_fmt(sel_mun)}"
    else:
        if not has_setor:
            st.error("❌ Colunas de setor não disponíveis")
            st.stop()
        setor_options = sorted(df_scope["CD_SETOR"].dropna().unique()) if "CD_SETOR" in df_scope.columns else []
        if len(setor_options)==0:
            st.error("❌ Nenhum setor disponível para o município selecionado")
            st.stop()
        sel_setor = st.selectbox(UI_CFG.get('labels', {}).get('select_setor', "Setor — selecione ou digite"), options=setor_options, key="sel_setor_analysis")
        df_analysis = df_scope[df_scope["CD_SETOR"]==sel_setor]
        title_suffix = f"Setor {sel_setor} — {_fmt(sel_mun)}"
else:
    df_analysis = df_long
    title_suffix = "Total filtrado"

# Agregação dos dados para visualização
df_plot = _aggregate_local(df_analysis)

# Padroniza e restringe categorias de faixas etárias ao conjunto canônico
df_plot = _pad_pyramid_categories(df_plot)
try:
    _faixas_can = DEMOG_CFG.get('age_buckets_order', [
        "0 a 4 anos", "5 a 9 anos", "10 a 14 anos", "15 a 19 anos",
        "20 a 24 anos", "25 a 29 anos", "30 a 39 anos", "40 a 49 anos",
        "50 a 59 anos", "60 a 69 anos", "70 anos ou mais"
    ])
    df_plot = df_plot[df_plot["faixa_etaria"].isin(_faixas_can)]
except Exception:
    pass

if df_plot.empty:
    st.warning("⚠️ Nenhum dado disponível para os filtros selecionados")
    st.write("DEBUG - Dados de análise:", len(df_analysis))
    if not df_analysis.empty:
        st.write("Colunas disponíveis:", list(df_analysis.columns))
        st.write("Amostra:", df_analysis.head())
    st.stop()

"""
Renderização dos gráficos com legendas ABNT, altura fixa do bloco de título e borda.
"""
# Guardar legendas exibidas para compor uma Lista de Figuras (recomendação ABNT)
fig_captions: list[str] = []

if comp_available and 'df_comp_plot' in locals() and isinstance(df_comp_plot, pd.DataFrame) and not df_comp_plot.empty:
    # Apenas duas colunas para as pirâmides; resumo vai para baixo
    col_left, col_mid = st.columns(2)

    with col_left:
        _left_hdr = UI_CFG.get('labels', {}).get('municipio_pyramid', "Pirâmide Etária — Município")
        _left_title = _sanitize_title(title_suffix)
        _left_caption = f"Figura 1 — {_left_hdr}: {_left_title}"
        fig_captions.append(_left_caption)
        st.markdown(f"<div class='abnt-figure'><div class='abnt-caption'><strong>{_left_caption}</strong></div></div>", unsafe_allow_html=True)
        try:
            fig = _construir_piramide(
                df_plot.rename(columns={"faixa_etaria": "idade_grupo", "populacao": "valor"}),
                title=_wrap_title(f"{_left_title}")
            )
            fig.update_layout(
                showlegend=False,
                yaxis_title=None,
                title=None,
                title_text=None,
                shapes=[dict(type='rect', x0=0, y0=0, x1=1, y1=1, xref='paper', yref='paper',
                             line=dict(color='black', width=2), fillcolor='rgba(0,0,0,0)')]
            )
            fig.update_traces(text=None, hovertemplate="Faixa: %{y}<br>População: %{x:,}")
        except Exception:
            fig = go.Figure()
    st.plotly_chart(fig, use_container_width=True, key="demog_pyr_main")
    st.markdown(f"<div class='abnt-figure'><div class='abnt-source'>{UI_CFG.get('labels', {}).get('source_text_chart', 'Fonte: IBGE')}</div></div>", unsafe_allow_html=True)

    with col_mid:
        _mid_hdr = UI_CFG.get('labels', {}).get('comparator_pyramid', "Pirâmide Etária — Comparador (em %)")
        _mid_title = _sanitize_title(locals().get('comp_title', None))
        _mid_caption = f"Figura 2 — {_mid_hdr}: {_mid_title}"
        fig_captions.append(_mid_caption)
        st.markdown(f"<div class='abnt-figure'><div class='abnt-caption'><strong>{_mid_caption}</strong></div></div>", unsafe_allow_html=True)
        try:
            _dfc = _pad_pyramid_categories(df_comp_plot.copy())
            try:
                _dfc = _dfc[_dfc["faixa_etaria"].isin(_faixas_can)]
            except Exception:
                pass
            _totalc = float(_dfc["populacao"].sum()) if not _dfc.empty else 0.0
            _dfc["populacao"] = (_dfc["populacao"].astype(float) / _totalc * 100.0) if _totalc > 0 else 0.0
            figc = _construir_piramide(
                _dfc.rename(columns={"faixa_etaria": "idade_grupo", "populacao": "valor"}),
                title=_wrap_title(f"{_mid_title}")
            )
            figc.update_yaxes(showticklabels=False, title_text=None)
            figc.update_xaxes(ticksuffix="%", title_text="% da População")
            figc.update_layout(
                showlegend=False,
                title=None,
                title_text=None,
                shapes=[dict(type='rect', x0=0, y0=0, x1=1, y1=1, xref='paper', yref='paper',
                             line=dict(color='black', width=2), fillcolor='rgba(0,0,0,0)')]
            )
            try:
                faixas_ordem = DEMOG_CFG.get('age_buckets_order', [
                    "0 a 4 anos", "5 a 9 anos", "10 a 14 anos", "15 a 19 anos",
                    "20 a 24 anos", "25 a 29 anos", "30 a 39 anos", "40 a 49 anos",
                    "50 a 59 anos", "60 a 69 anos", "70 anos ou mais"
                ])
                figc.update_yaxes(categoryorder='array', categoryarray=faixas_ordem)
            except Exception:
                pass
            figc.update_traces(text=None, hovertemplate="Faixa: %{y}<br>% População: %{x:.1f}%")
        except Exception:
            figc = go.Figure()
    st.plotly_chart(figc, use_container_width=True, key="demog_pyr_comp")
    st.markdown(f"<div class='abnt-figure'><div class='abnt-source'>{UI_CFG.get('labels', {}).get('source_text_chart', 'Fonte: IBGE')}</div></div>", unsafe_allow_html=True)

    # Resumos abaixo das pirâmides: município e comparador
    st.markdown("\n")
    st.subheader(UI_CFG.get('labels', {}).get('population_summary_both', "📈 Resumo Populacional"))
    s1, s2 = st.columns(2)
    with s1:
        st.markdown("**Município**")
        total_pop = int(df_plot["populacao"].sum())
        pop_masc = int(df_plot[df_plot["sexo"] == "Masculino"]["populacao"].sum())
        pop_fem = int(df_plot[df_plot["sexo"] == "Feminino"]["populacao"].sum())
        st.metric("População Total", _fmt_br(total_pop, 0))
        st.metric("População Masculina", _fmt_br(pop_masc, 0), f"{_fmt_br(pop_masc/total_pop*100, 1)}%" if total_pop > 0 else None)
        st.metric("População Feminina", _fmt_br(pop_fem, 0), f"{_fmt_br(pop_fem/total_pop*100, 1)}%" if total_pop > 0 else None)
    with s2:
        st.markdown(f"**Comparador — {_sanitize_title(locals().get('comp_title', None))}**")
        if isinstance(df_comp_plot, pd.DataFrame) and not df_comp_plot.empty:
            _totc2 = int(df_comp_plot["populacao"].sum())
            _masc2 = int(df_comp_plot[df_comp_plot["sexo"] == "Masculino"]["populacao"].sum())
            _fem2 = int(df_comp_plot[df_comp_plot["sexo"] == "Feminino"]["populacao"].sum())
            st.metric("População Total", _fmt_br(_totc2, 0))
            st.metric("População Masculina", _fmt_br(_masc2, 0), f"{_fmt_br(_masc2/_totc2*100, 1)}%" if _totc2 > 0 else None)
            st.metric("População Feminina", _fmt_br(_fem2, 0), f"{_fmt_br(_fem2/_totc2*100, 1)}%" if _totc2 > 0 else None)
        else:
            st.info("Sem comparador disponível para este recorte.")

else:
    # Uma única pirâmide com resumo abaixo
    _single_hdr = UI_CFG.get('labels', {}).get('generic_pyramid', "Pirâmide Etária")
    _single_title = _sanitize_title(title_suffix)
    _single_caption = f"Figura 1 — {_single_hdr}: {_single_title}"
    fig_captions.append(_single_caption)
    st.markdown(f"<div class='abnt-figure'><div class='abnt-caption'><strong>{_single_caption}</strong></div></div>", unsafe_allow_html=True)
    try:
        fig = _construir_piramide(
            df_plot.rename(columns={"faixa_etaria": "idade_grupo", "populacao": "valor"}),
            title=_wrap_title(f"Demografia — {_single_title}")
        )
        fig.update_layout(
            showlegend=False,
            yaxis_title=None,
            title=None,
            title_text=None,
            shapes=[dict(type='rect', x0=0, y0=0, x1=1, y1=1, xref='paper', yref='paper',
                         line=dict(color='black', width=2), fillcolor='rgba(0,0,0,0)')]
        )
        fig.update_traces(text=None)
    except Exception:
        fig = go.Figure()
    st.plotly_chart(fig, use_container_width=True, key="demog_pyr_single")
    st.markdown(f"<div class='abnt-figure'><div class='abnt-source'>{UI_CFG.get('labels', {}).get('source_text_chart', 'Fonte: IBGE')}</div></div>", unsafe_allow_html=True)

    st.markdown("\n")
    st.subheader(UI_CFG.get('labels', {}).get('population_summary', "📈 Resumo Populacional"))
    total_pop = int(df_plot["populacao"].sum())
    pop_masc = int(df_plot[df_plot["sexo"] == "Masculino"]["populacao"].sum())
    pop_fem = int(df_plot[df_plot["sexo"] == "Feminino"]["populacao"].sum())
    st.metric("População Total", _fmt_br(total_pop, 0))
    st.metric("População Masculina", _fmt_br(pop_masc, 0), f"{_fmt_br(pop_masc/total_pop*100, 1)}%" if total_pop > 0 else None)
    st.metric("População Feminina", _fmt_br(pop_fem, 0), f"{_fmt_br(pop_fem/total_pop*100, 1)}%" if total_pop > 0 else None)

# Lista de Figuras (opcional)
if fig_captions:
    st.markdown(f"**{UI_CFG.get('labels', {}).get('list_of_figures_title', 'Lista de Figuras')}**")
    for cap in fig_captions:
        st.markdown(f"- {cap}")

st.divider()
st.subheader(UI_CFG.get('labels', {}).get('table_title', "📋 Tabela Demográfica"))

# Barra de progresso para montagem da tabela
if hasattr(st, "status"):
    with st.status("Montando tabela…", expanded=False) as st_status:
        ptab = st.progress(0, text="Agregando linhas…")
        abnt_table = create_abnt_demographic_table(df_plot)
        ptab.progress(50, text="Calculando comparação…")
        # Quando houver comparador, calcular diferenças proporcionais por faixa etária (pp)
        comp_table = None
        if 'df_comp_plot' in locals() and df_comp_plot is not None and isinstance(df_comp_plot, pd.DataFrame) and not df_comp_plot.empty:
            try:
                comp_table = create_abnt_demographic_table(_pad_pyramid_categories(df_comp_plot))
                # % do Total (principal)
                total_main = float(abnt_table.loc[abnt_table['Faixa Etária']=="TOTAL", 'Total'].iloc[0]) if not abnt_table.empty else 0.0
                abnt_table['% do Total'] = abnt_table.apply(
                    lambda r: round((float(r['Total'])/total_main*100.0), 1) if r['Faixa Etária'] != 'TOTAL' and total_main>0 else (100.0 if r['Faixa Etária']=='TOTAL' else 0.0),
                    axis=1
                )
                # % do Total (comparador)
                total_comp = float(comp_table.loc[comp_table['Faixa Etária']=="TOTAL", 'Total'].iloc[0]) if not comp_table.empty else 0.0
                comp_pct = comp_table[['Faixa Etária','Total']].copy()
                comp_pct['% do Total (Comp)'] = comp_pct.apply(
                    lambda r: round((float(r['Total'])/total_comp*100.0), 1) if r['Faixa Etária'] != 'TOTAL' and total_comp>0 else (100.0 if r['Faixa Etária']=='TOTAL' else 0.0),
                    axis=1
                )
                comp_pct = comp_pct[['Faixa Etária','% do Total (Comp)']]
                # Merge e delta (pp)
                abnt_table = abnt_table.merge(comp_pct, on='Faixa Etária', how='left')
                abnt_table['Δ vs Comp.'] = abnt_table.apply(
                    lambda r: (r['% do Total'] - r['% do Total (Comp)']) if pd.notna(r.get('% do Total (Comp)')) and r['Faixa Etária'] != 'TOTAL' else None,
                    axis=1
                )
                # Reordenar colunas: inserir % do Total e Δ vs Comp. após '% Feminino'
                cols = list(abnt_table.columns)
                base_order = ['Faixa Etária', 'Masculino', 'Feminino', 'Total', '% Masculino', '% Feminino']
                extra = ['% do Total', 'Δ vs Comp.']
                if '% do Total (Comp)' in cols:
                    cols.remove('% do Total (Comp)')
                ordered = [c for c in base_order if c in cols] + [c for c in extra if c in cols] + [c for c in cols if c not in set(base_order+extra)]
                abnt_table = abnt_table[ordered]
            except Exception:
                comp_table = None
        ptab.progress(100)
        st_status.update(label="Tabela pronta", state="complete")
else:
    abnt_table = create_abnt_demographic_table(df_plot)
    # Quando houver comparador, calcular diferenças proporcionais por faixa etária (pp)
    comp_table = None
    if 'df_comp_plot' in locals() and df_comp_plot is not None and isinstance(df_comp_plot, pd.DataFrame) and not df_comp_plot.empty:
        try:
            comp_table = create_abnt_demographic_table(_pad_pyramid_categories(df_comp_plot))
            total_main = float(abnt_table.loc[abnt_table['Faixa Etária']=="TOTAL", 'Total'].iloc[0]) if not abnt_table.empty else 0.0
            abnt_table['% do Total'] = abnt_table.apply(
                lambda r: round((float(r['Total'])/total_main*100.0), 1) if r['Faixa Etária'] != 'TOTAL' and total_main>0 else (100.0 if r['Faixa Etária']=='TOTAL' else 0.0),
                axis=1
            )
            total_comp = float(comp_table.loc[comp_table['Faixa Etária']=="TOTAL", 'Total'].iloc[0]) if not comp_table.empty else 0.0
            comp_pct = comp_table[['Faixa Etária','Total']].copy()
            comp_pct['% do Total (Comp)'] = comp_pct.apply(
                lambda r: round((float(r['Total'])/total_comp*100.0), 1) if r['Faixa Etária'] != 'TOTAL' and total_comp>0 else (100.0 if r['Faixa Etária']=='TOTAL' else 0.0),
                axis=1
            )
            comp_pct = comp_pct[['Faixa Etária','% do Total (Comp)']]
            abnt_table = abnt_table.merge(comp_pct, on='Faixa Etária', how='left')
            abnt_table['Δ vs Comp.'] = abnt_table.apply(
                lambda r: (r['% do Total'] - r['% do Total (Comp)']) if pd.notna(r.get('% do Total (Comp)')) and r['Faixa Etária'] != 'TOTAL' else None,
                axis=1
            )
            cols = list(abnt_table.columns)
            base_order = ['Faixa Etária', 'Masculino', 'Feminino', 'Total', '% Masculino', '% Feminino']
            extra = ['% do Total', 'Δ vs Comp.']
            if '% do Total (Comp)' in cols:
                cols.remove('% do Total (Comp)')
            ordered = [c for c in base_order if c in cols] + [c for c in extra if c in cols] + [c for c in cols if c not in set(base_order+extra)]
            abnt_table = abnt_table[ordered]
        except Exception:
            comp_table = None

 

# Título da tabela conforme ABNT, com indicação de filtros de setores
subset_flag = False
try:
    # Situação: compara seleção atual com universo disponível
    if "SITUACAO" in df_long_full.columns:
        all_situ = sorted([x for x in pd.Series(df_long_full["SITUACAO"]).dropna().unique() if x in ("Urbana","Rural")])
        sel_situ = st.session_state.get("fil_situacao_demog", None)
        if all_situ:
            if sel_situ is None:
                # Sem estado salvo, assume que não é subset apenas para não marcar indevidamente
                pass
            else:
                # Se seleção difere do universo, é subset
                if set(sel_situ) != set(all_situ):
                    subset_flag = True
    # Tipo: compara seleção atual com universo disponível
    if "CD_TIPO" in df_long_full.columns:
        all_tipo = sorted([int(x) for x in pd.Series(df_long_full["CD_TIPO"]).dropna().unique()])
        sel_tipo_state = st.session_state.get("fil_tipo_demog", [])
        sel_tipo_codes = [int(k) for k, _ in sel_tipo_state] if (sel_tipo_state and isinstance(sel_tipo_state[0], tuple)) else [int(x) for x in sel_tipo_state] if sel_tipo_state else []
        if all_tipo:
            if set(sel_tipo_codes) != set(all_tipo):
                subset_flag = True
except Exception:
    pass

table_note = " — setores selecionados" if subset_flag else ""
# Numeração simples (há apenas uma tabela nesta página)
tabela_num = 1
_title_html = f"""
<div style="text-align:center; font-family: Arial, 'Times New Roman', serif; font-size: 11pt; font-weight: bold;">
    {UI_CFG.get('labels', {}).get('table_title_prefix', 'Tabela')} {tabela_num} — Distribuição da população por faixa etária e sexo — {_sanitize_title(title_suffix)}{table_note}
</div>
"""
st.markdown(_title_html, unsafe_allow_html=True)

# Renderização ABNT: aberta nas laterais (sem bordas verticais), linhas superior e inferior
def _render_abnt_table_html(df: pd.DataFrame) -> str:
    # Formatação numérica
    fmt = {
        "Masculino": lambda x: _fmt_br(x, 0),
        "Feminino": lambda x: _fmt_br(x, 0),
        "Total": lambda x: _fmt_br(x, 0),
        "% Masculino": lambda x: (_fmt_br(x, 1) + "%") if pd.notna(x) else "",
        "% Feminino": lambda x: (_fmt_br(x, 1) + "%") if pd.notna(x) else "",
        "% do Total": lambda x: (_fmt_br(x, 1) + "%") if pd.notna(x) else "",
        "Δ vs Comp.": None,
    }
    df_fmt = df.copy()
    # Formatação especial do delta com setas/cores
    def _fmt_delta(val):
        if pd.isna(val):
            return ""
        try:
            v = float(val)
        except Exception:
            return ""
        if abs(v) < 1e-9:
            return "<span style='color:#666'>—</span>"
        arrow = "▲" if v > 0 else "▼"
        color = "#0a8f2a" if v > 0 else "#c62828"
        sign = "+" if v > 0 else ""
        return f"<span style='color:{color}; font-weight:600'>{arrow} {sign}{_fmt_br(abs(v), 1)} pp</span>"
    for col, f in fmt.items():
        if col in df_fmt.columns:
            if col == "Δ vs Comp.":
                df_fmt[col] = df_fmt[col].apply(lambda x: _fmt_delta(x))
            else:
                df_fmt[col] = df_fmt[col].apply(lambda x: f(x) if pd.notna(x) else "")

    # Construir HTML manual para ter controle total sobre as bordas
    thead = "<tr>" + "".join(f"<th>{c}</th>" for c in df_fmt.columns) + "</tr>"
    rows = []
    for _, r in df_fmt.iterrows():
        tds = "".join(f"<td>{r[c]}</td>" for c in df_fmt.columns)
        rows.append(f"<tr>{tds}</tr>")
    tbody = "".join(rows)
    css = """
    <style>
    table.abnt {border-collapse: collapse; width: 100%; border-top: 2px solid #000; border-bottom: 2px solid #000; font-family: Arial, 'Times New Roman', serif; font-size: 12px;}
    table.abnt th, table.abnt td {padding: 6px 10px; text-align: right; border-left: none; border-right: none;}
    table.abnt th:first-child, table.abnt td:first-child {text-align: left;}
    table.abnt thead th {text-align: left;}
    </style>
    """
    html = f"{css}<table class='abnt'><thead>{thead}</thead><tbody>{tbody}</tbody></table>"
    return html

st.markdown(_render_abnt_html(abnt_table), unsafe_allow_html=True)

# Fonte imediatamente abaixo da tabela (ABNT) — tamanho menor
st.markdown(f"<div style='font-size:10pt; text-align:left;'>{UI_CFG.get('labels', {}).get('source_text_table', 'Fonte: IBGE')}</div>", unsafe_allow_html=True)

csv_abnt = abnt_table.to_csv(index=False, encoding='utf-8-sig')
dataframe_to_csv_download(
    abnt_table,
    file_name=f"tabela_demografica_{_sanitize_title(title_suffix).replace(' ', '_')}.csv",
    label="📥 Baixar Tabela (CSV)",
)

# Notas explicativas (apresentação) — filtros aplicados e registros com valores ausentes
def _build_scope_full(df_full: pd.DataFrame, df_scope_like: pd.DataFrame) -> pd.DataFrame:
    """Gera df_full recortado pela escala selecionada, sem aplicar filtros de Situação/Tipo.
    Usa as chaves regionais presentes em df_scope_like (que já tem a escala escolhida).
    """
    base = df_full
    # Preferir CD_SETOR quando seleção for de um setor específico
    if "CD_SETOR" in df_scope_like.columns and df_scope_like["CD_SETOR"].nunique() == 1:
        sel = df_scope_like["CD_SETOR"].dropna().unique().tolist()
        if sel:
            return base[base["CD_SETOR"].isin(sel)] if "CD_SETOR" in base.columns else base
    # Município
    if "CD_MUN" in df_scope_like.columns and df_scope_like["CD_MUN"].nunique() >= 1:
        muns = df_scope_like["CD_MUN"].dropna().unique().tolist()
        if muns and "CD_MUN" in base.columns:
            return base[base["CD_MUN"].isin(muns)]
    # Regiões
    if {"TIPO_RM_AU","NOME_RM_AU"}.issubset(df_scope_like.columns) and {"TIPO_RM_AU","NOME_RM_AU"}.issubset(base.columns):
        pares = (
            df_scope_like[["TIPO_RM_AU","NOME_RM_AU"]]
            .dropna().drop_duplicates().itertuples(index=False, name=None)
        )
        mask = pd.Series([False] * len(base))
        for t, n in pares:
            mask |= (base["TIPO_RM_AU"].astype(str).str.upper() == str(t).upper()) & (base["NOME_RM_AU"] == n)
        return base[mask]
    # Fallback RM/AU legado
    if "RM_NOME" in df_scope_like.columns and "RM_NOME" in base.columns and df_scope_like["RM_NOME"].notna().any():
        rms = df_scope_like["RM_NOME"].dropna().unique().tolist()
        return base[base["RM_NOME"].isin(rms)]
    if "AU_NOME" in df_scope_like.columns and "AU_NOME" in base.columns and df_scope_like["AU_NOME"].notna().any():
        aus = df_scope_like["AU_NOME"].dropna().unique().tolist()
        return base[base["AU_NOME"].isin(aus)]
    # Região Imediata/Intermediária
    if "NM_RGI" in df_scope_like.columns and "NM_RGI" in base.columns and df_scope_like["NM_RGI"].notna().any():
        rgis = df_scope_like["NM_RGI"].dropna().unique().tolist()
        return base[base["NM_RGI"].isin(rgis)]
    if "NM_RGINT" in df_scope_like.columns and "NM_RGINT" in base.columns and df_scope_like["NM_RGINT"].notna().any():
        rgints = df_scope_like["NM_RGINT"].dropna().unique().tolist()
        return base[base["NM_RGINT"].isin(rgints)]
    # Estado (tudo)
    return base

try:
    # Base completa no mesmo recorte de escala (sem filtros Situação/Tipo)
    df_scope_full = _build_scope_full(df_long_full, df_analysis if 'df_analysis' in locals() else df_long)

    # Situação: incluídas vs excluídas dentro do recorte
    situ_opts_scope = []
    if "SITUACAO" in df_scope_full.columns:
        situ_opts_scope = sorted([x for x in df_scope_full["SITUACAO"].dropna().unique() if x in ("Urbana","Rural")])
    sel_situ = st.session_state.get("fil_situacao_demog", None)
    if sel_situ is None:
        sel_situ = sorted(df_long["SITUACAO"].dropna().unique().tolist()) if "SITUACAO" in df_long.columns else []
    inclu_situ = [s for s in sel_situ if s in ("Urbana","Rural")]
    exclu_situ = [s for s in situ_opts_scope if s not in inclu_situ]

    # Tipo de setor: incluídos vs excluídos dentro do recorte
    tipos_scope = []
    if "CD_TIPO" in df_scope_full.columns:
        tipos_scope = sorted([int(x) for x in pd.Series(df_scope_full["CD_TIPO"]).dropna().unique()])
    sel_tipo = st.session_state.get("fil_tipo_demog", None)
    if sel_tipo is not None and isinstance(sel_tipo, list) and len(sel_tipo) > 0 and isinstance(sel_tipo[0], tuple):
        inclu_tipo_codes = [int(k) for k, _ in sel_tipo]
    else:
        inclu_tipo_codes = sorted([int(x) for x in pd.Series(df_long.get("CD_TIPO", pd.Series(dtype=float))).dropna().unique()]) if "CD_TIPO" in df_long.columns else []
    exclu_tipo_codes = [c for c in tipos_scope if c not in inclu_tipo_codes]

    def _tipo_label(c: int) -> str:
        return f"{c} — {TIPO_MAP.get(c, 'Desconhecido')}"

    # Contagem de setores com valores ausentes/anônimos na escala
    null_note = None
    if "CD_SETOR" in df_scope_full.columns:
        # Normaliza coluna de valor
        val_col = "valor" if "valor" in df_scope_full.columns else ("populacao" if "populacao" in df_scope_full.columns else None)
        if val_col is None:
            # tenta derivar a partir de df_long (já renomeado)
            val_col = "populacao" if "populacao" in df_long.columns else None
        if val_col is not None:
            g = df_scope_full[["CD_SETOR", val_col]].copy()
            g[val_col] = pd.to_numeric(g[val_col], errors="coerce")
            total_setores = int(g["CD_SETOR"].nunique())
            setores_com_nulos = int(g.groupby("CD_SETOR")[val_col].apply(lambda s: s.isna().any()).sum()) if total_setores > 0 else 0
            perc_nulos = (setores_com_nulos / total_setores * 100.0) if total_setores > 0 else 0.0
            null_note = f"Registros de setor com valores ausentes/anônimos no recorte: {_fmt_br(setores_com_nulos,0)} de {_fmt_br(total_setores,0)} setores ({_fmt_br(perc_nulos,1)}%)."
    # Render das notas
    st.markdown(UI_CFG.get('labels', {}).get('notes_title', "**Notas**"))
    itens = []
    # Nota 1: filtros de inclusão/exclusão
    if inclu_situ or exclu_situ:
        itens.append(f"Situação incluída: {', '.join(inclu_situ) if inclu_situ else '—'}; excluída: {', '.join(exclu_situ) if exclu_situ else '—'}.")
    if inclu_tipo_codes or exclu_tipo_codes:
        itens.append(
            "Tipo de setor incluído: " + (", ".join([_tipo_label(c) for c in inclu_tipo_codes]) if inclu_tipo_codes else '—') +
            "; excluído: " + (", ".join([_tipo_label(c) for c in exclu_tipo_codes]) if exclu_tipo_codes else '—') + "."
        )
    if null_note:
        itens.append(null_note)
    if itens:
        # Enumerar como (a), (b), (c) …
        letras = [chr(ord('a') + i) for i in range(len(itens))]
        st.markdown("\n".join([f"({letras[i]}) {itens[i]}" for i in range(len(itens))]))
except Exception:
    # Silencioso: notas são best-effort e não devem quebrar a página
    pass

# Rodapé com fonte dos dados
st.divider()
st.caption("Fonte: Censo 2022 — IBGE · Página: https://www.ibge.gov.br/estatisticas/sociais/populacao/22827-censo-demografico-2022.html?=&t=downloads")
