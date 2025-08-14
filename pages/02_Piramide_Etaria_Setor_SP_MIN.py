import sys
from pathlib import Path as _P
import streamlit as st
import pandas as pd

SRC = _P(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from censo_app.transform import load_sp_age_sex_enriched, wide_to_long_pyramid
from censo_app.viz import make_age_pyramid

st.set_page_config(layout="wide")
st.title("👁️‍🗨️ Pirâmide Etária — 1 Setor (SP) — v1.7")

def _norm(s: str) -> str:
    return (s or "").strip().strip('"').strip("'").replace("\\", "/")

parquet_path = st.text_input("Parquet (SP)", r"D:\\repo\\saida_parquet\\base_integrada_final.parquet", key="path_parquet_min")
parquet_path = _norm(parquet_path)

@st.cache_data(show_spinner=True)
def _load_wide(path: str) -> pd.DataFrame:
    return load_sp_age_sex_enriched(path, limit=None, verbose=False, uf_code="35")

try:
    df_wide = _load_wide(parquet_path)
    st.success(f"{len(df_wide):,} linhas (setores) lidas.")
except Exception as e:
    st.error(f"Falha ao ler Parquet: {e}")
    st.stop()

left, mid, right = st.columns([1,1,1])

# filtro macro se existir
if "SITUACAO" in df_wide.columns:
    macro_opts = sorted([x for x in df_wide["SITUACAO"].dropna().unique().tolist() if x in ("Urbana","Rural")]) or ["Urbana","Rural"]
    sel_macro = left.multiselect("Situação (Urbana/Rural)", macro_opts, default=macro_opts, key="macro_min")
    if sel_macro:
        df_wide = df_wide[df_wide["SITUACAO"].isin(sel_macro)]

# município
if set(["CD_MUN","NM_MUN"]).issubset(df_wide.columns):
    mun_df = df_wide[["CD_MUN","NM_MUN"]].dropna().drop_duplicates().sort_values(["NM_MUN","CD_MUN"])
    mun_options = [None] + mun_df["CD_MUN"].tolist()
    name_map = dict(zip(mun_df["CD_MUN"], mun_df["NM_MUN"]))
    sel_mun = mid.selectbox("Município", options=mun_options, format_func=lambda c: "— selecione —" if c is None else f"{c} — {name_map.get(c,'')}", key="mun_min")
    if sel_mun is None:
        st.info("Selecione um município para habilitar a lista de setores.")
        st.stop()
    df_mun = df_wide[df_wide["CD_MUN"] == sel_mun]
else:
    st.error("Colunas CD_MUN/NM_MUN ausentes na base.")
    st.stop()

# setor
label_det = "SITUACAO_DET_TXT" if "SITUACAO_DET_TXT" in df_mun.columns else None
if "CD_SETOR" in df_mun.columns:
    cols_sel = ["CD_SETOR"] + ([label_det] if label_det else [])
    set_df = df_mun[cols_sel].dropna().drop_duplicates().sort_values("CD_SETOR")
    setor_options = [None] + set_df["CD_SETOR"].tolist()
    det_map = dict(zip(set_df["CD_SETOR"], set_df[label_det])) if label_det else {}
    sel_setor = right.selectbox("Setor", options=setor_options, format_func=lambda c: "— selecione —" if c is None else (f"{c} — {det_map.get(c,'')}" if det_map else str(c)), key="setor_min")
    if sel_setor is None:
        st.info("Selecione um setor para ver a pirâmide.")
        st.stop()
else:
    st.error("Coluna CD_SETOR ausente na base.")
    st.stop()

st.divider()

df_sector = df_mun[df_mun["CD_SETOR"] == sel_setor].copy()
if df_sector.empty:
    st.warning("Setor sem linhas após filtros.")
    st.stop()

df_long = wide_to_long_pyramid(df_sector)
df_plot = df_long.groupby(["idade_grupo","sexo"], as_index=False)["valor"].sum()

colA, colB = st.columns([2,1])
fig = make_age_pyramid(df_plot, title=f"Setor {sel_setor}")
colA.plotly_chart(fig, use_container_width=True)
colB.dataframe(df_plot.head(50))
