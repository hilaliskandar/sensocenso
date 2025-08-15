import sys
from pathlib import Path as _P
import streamlit as st
import pandas as pd
import plotly.graph_objects as go



SRC = _P(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from censo_app.transform import load_sp_age_sex_enriched, wide_to_long_pyramid, SITUACAO_DET_MAP, TIPO_MAP
from censo_app.indicadores_demograficos import calcular_indicadores_df
from censo_app.transform import VARIAVEL_DESCRICAO
from censo_app.viz import make_age_pyramid

st.set_page_config(layout="wide")
st.title("🏛️ Pirâmide Etária — SP (setor / município) — v1.9.1")

with st.sidebar:
    keepalive = st.checkbox("Evitar expirar (autorefresh a cada 5 min)", value=False)
    if keepalive:
        st.info("Para ativar o autorefresh instale: pip install streamlit-autorefresh")

def _norm(s: str) -> str:
    return (s or "").strip().strip('"').strip("'").replace("\\", "/")

parquet_path = st.text_input("Parquet (SP)", st.session_state.get("parquet_path", r"D:\\repo\\saida_parquet\\base_integrada_final.parquet"), key="parquet_path")
parquet_path = _norm(parquet_path)

@st.cache_data(show_spinner=True, ttl=3600)
def _load_wide(path: str) -> pd.DataFrame:
    return load_sp_age_sex_enriched(path, limit=None, verbose=False, uf_code="35")

try:
    df_wide = _load_wide(parquet_path)
    st.success(f"{len(df_wide):,} linhas (setores) lidas.")
except Exception as e:
    st.error(f"Falha ao ler Parquet: {e}")
    st.stop()

with st.expander("Filtros", expanded=True):
    c1,c2,c3 = st.columns(3)
    if "SITUACAO" in df_wide.columns:
        macro_opts = sorted([x for x in df_wide["SITUACAO"].dropna().unique().tolist() if x in ("Urbana","Rural")]) or ["Urbana","Rural"]
        sel_macro = c1.multiselect("Situação (Urbana/Rural)", macro_opts, default=st.session_state.get("sel_macro", macro_opts), key="sel_macro")
        if sel_macro: df_wide = df_wide[df_wide["SITUACAO"].isin(sel_macro)]
    if "CD_SITUACAO" in df_wide.columns:
        sit_opts = list(SITUACAO_DET_MAP.items())
        default_sit = st.session_state.get("sel_sit", sit_opts)
        sel_sit = c2.multiselect("Situação detalhada (CD_SITUACAO)", sit_opts, default=default_sit, format_func=lambda t: f"{t[0]} — {t[1]}", key="sel_sit")
        if sel_sit: df_wide = df_wide[df_wide["CD_SITUACAO"].isin([k for k,_ in sel_sit])]
    if "CD_TIPO" in df_wide.columns:
        tipo_opts = list(TIPO_MAP.items())
        default_tipo = st.session_state.get("sel_tipo", tipo_opts)
        sel_tipo = c3.multiselect("Tipo do Setor (CD_TIPO)", tipo_opts, default=default_tipo, format_func=lambda t: f"{t[0]} — {t[1]}", key="sel_tipo")
        if sel_tipo: df_wide = df_wide[df_wide["CD_TIPO"].isin([k for k,_ in sel_tipo])]

# município
if set(["CD_MUN","NM_MUN"]).issubset(df_wide.columns):
    mun_df = df_wide[["CD_MUN","NM_MUN"]].dropna().drop_duplicates().sort_values(["NM_MUN","CD_MUN"])
    name_map = dict(zip(mun_df["CD_MUN"], mun_df["NM_MUN"]))
    options_mun = [None]+mun_df["CD_MUN"].tolist()
    default_mun = st.session_state.get("sel_mun", None)
    idx = options_mun.index(default_mun) if default_mun in options_mun else 0
    sel_mun = st.selectbox("Município", options=options_mun, index=idx,
                           format_func=lambda c: "— selecione —" if c is None else f"{c} — {name_map.get(c,'')}", key="sel_mun")
    if sel_mun is None:
        st.info("Selecione um município para continuar.")
        st.stop()
    df_mun = df_wide[df_wide["CD_MUN"] == sel_mun]
else:
    st.error("Colunas CD_MUN/NM_MUN ausentes na base.")
    st.stop()

modo = st.radio("Modo de visualização:", ["Lista de setores","Pirâmide do município (total)","Pirâmide de um setor"], horizontal=True, key="modo")

def _agg_long(df_long: pd.DataFrame) -> pd.DataFrame:
    piv = df_long.pivot_table(index="idade_grupo", columns="sexo", values="valor", aggfunc="sum", fill_value=0).reset_index()
    if "Masculino" not in piv.columns: piv["Masculino"] = 0
    if "Feminino" not in piv.columns: piv["Feminino"] = 0
    piv["Total_faixa"] = piv["Masculino"] + piv["Feminino"]
    return piv

def _pie_mf(m_total: int, f_total: int, title: str) -> go.Figure:
    fig = go.Figure(data=[go.Pie(labels=["Masculino","Feminino"], values=[m_total,f_total], hole=0.3)])
    fig.update_layout(title=title, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig

if modo == "Lista de setores":
    cols_show = [c for c in ["CD_SETOR","SITUACAO","CD_SITUACAO","SITUACAO_DET_TXT","CD_TIPO","TP_SETOR_TXT","AREA_KM2","V0001"] if c in df_mun.columns]
    st.write(f"**{len(df_mun)}** setores no município selecionado.")
    st.dataframe(df_mun[cols_show].drop_duplicates().sort_values("CD_SETOR"), use_container_width=True, height=600)
    st.stop()

# MUNICÍPIO TOTAL
if modo == "Pirâmide do município (total)":
    df_long = wide_to_long_pyramid(df_mun)
    df_plot = df_long.groupby(["idade_grupo","sexo"], as_index=False)["valor"].sum()

    tbl = _agg_long(df_plot)
    total_mf = int(tbl["Total_faixa"].sum())
    total_decl = int(pd.to_numeric(df_mun.get("V0001"), errors="coerce").fillna(0).sum()) if "V0001" in df_mun.columns else None
    m_total = int(df_plot[df_plot["sexo"]=="Masculino"]["valor"].sum())
    f_total = int(df_plot[df_plot["sexo"]=="Feminino"]["valor"].sum())

    cA,cB = st.columns([2,1])
    cA.plotly_chart(make_age_pyramid(df_plot, title=f"Município {name_map.get(sel_mun,'')} — total"), use_container_width=True)
    cB.plotly_chart(_pie_mf(m_total, f_total, title="Sexo — total do município"), use_container_width=True)

    st.subheader("Verificação por faixa (município)")
    st.dataframe(tbl, use_container_width=True)
    st.write(f"**Soma M+F (todas as faixas):** {total_mf:,}")
if total_decl is not None:
    diff = total_mf - total_decl
    pct = (diff/total_decl*100) if total_decl else None
    st.write(f"**Total de pessoas (V0001):** {total_decl:,}")
    st.write(f"**Diferença (M+F − V0001):** {diff:+,}" + (f" ({pct:.3f}% do V0001)" if pct is not None else ""))

    # Calcular e exibir indicadores demográficos
st.subheader("Indicadores Demográficos — Município")
indicadores = calcular_indicadores_df(df_long)
for var, val in indicadores.items():
    desc = VARIAVEL_DESCRICAO.get(var, "")
    st.write(f"**{var}:** {val:.3f}  ", f"<span title='{desc}'>ℹ️</span>", unsafe_allow_html=True)
    st.stop()

# SETOR ESPECÍFICO
label_det = "SITUACAO_DET_TXT" if "SITUACAO_DET_TXT" in df_mun.columns else None
if "CD_SETOR" in df_mun.columns:
    cols_sel = ["CD_SETOR"] + ([label_det] if label_det else [])
    set_df = df_mun[cols_sel].dropna().drop_duplicates().sort_values("CD_SETOR")
    det_map = dict(zip(set_df["CD_SETOR"], set_df[label_det])) if label_det else {}
    options = [None] + set_df["CD_SETOR"].tolist()
    default_set = st.session_state.get("sel_setor", None)
    idx = options.index(default_set) if default_set in options else 0
    sel_setor = st.selectbox("Setor", options=options, index=idx,
                             format_func=lambda c: "— selecione —" if c is None else (f"{c} — {det_map.get(c,'')}" if det_map else str(c)), key="sel_setor")
    if sel_setor is None:
        st.info("Selecione um setor para ver a pirâmide e as checagens.")
        st.stop()
else:
    st.error("Coluna CD_SETOR ausente na base.")
    st.stop()

df_sector = df_mun[df_mun["CD_SETOR"] == sel_setor].copy()
df_long = wide_to_long_pyramid(df_sector)
df_plot = df_long.groupby(["idade_grupo","sexo"], as_index=False)["valor"].sum()

tbl = _agg_long(df_plot)
total_mf = int(tbl["Total_faixa"].sum())
total_decl = None
if "V0001" in df_sector.columns:
    uniq = pd.to_numeric(df_sector["V0001"], errors="coerce").dropna().unique()
    if len(uniq) == 1:
        total_decl = int(uniq[0])
    else:
        total_decl = int(pd.to_numeric(df_sector["V0001"], errors="coerce").fillna(0).sum())

m_total = int(df_plot[df_plot["sexo"]=="Masculino"]["valor"].sum())
f_total = int(df_plot[df_plot["sexo"]=="Feminino"]["valor"].sum())

cA,cB = st.columns([2,1])
cA.plotly_chart(make_age_pyramid(df_plot, title=f"Setor {sel_setor}"), use_container_width=True)
cB.plotly_chart(_pie_mf(m_total, f_total, title="Sexo — total do setor"), use_container_width=True)

st.subheader("Verificação por faixa (setor)")
st.dataframe(tbl, use_container_width=True)
st.write(f"**Soma M+F (todas as faixas):** {total_mf:,}")
if total_decl is not None:
    diff = total_mf - total_decl
    pct = (diff/total_decl*100) if total_decl else None
    st.write(f"**Total de pessoas (V0001 — 'Total de pessoas'):** {total_decl:,}")
    st.write(f"**Diferença (M+F − V0001):** {diff:+,}" + (f" ({pct:.3f}% do V0001)" if pct is not None else ""))
    # Calcular e exibir indicadores demográficos
    st.subheader("Indicadores Demográficos — Setor")
    indicadores = calcular_indicadores_df(df_long)
    for var, val in indicadores.items():
        desc = VARIAVEL_DESCRICAO.get(var, "")
        st.write(f"**{var}:** {val:.3f}  ", f"<span title='{desc}'>ℹ️</span>", unsafe_allow_html=True)
