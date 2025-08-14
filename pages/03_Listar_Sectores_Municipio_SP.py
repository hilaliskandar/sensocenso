import sys
from pathlib import Path as _P
import streamlit as st
import pandas as pd

SRC = _P(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from censo_app.transform import load_sp_age_sex_enriched

st.set_page_config(layout="wide")
st.title("📋 Lista de setores por município — v1.8")

def _norm(s: str) -> str:
    return (s or "").strip().strip('"').strip("'").replace("\\", "/")

parquet_path = st.text_input("Parquet (SP)", r"D:\\repo\\saida_parquet\\base_integrada_final.parquet", key="path_list")
parquet_path = _norm(parquet_path)

@st.cache_data(show_spinner=True)
def _load(path: str) -> pd.DataFrame:
    return load_sp_age_sex_enriched(path, verbose=False, uf_code="35")

try:
    df = _load(parquet_path)
    st.success(f"{len(df):,} linhas (SP)")
except Exception as e:
    st.error(f"Falha ao ler Parquet: {e}")
    st.stop()

if set(["CD_MUN","NM_MUN"]).issubset(df.columns):
    mun_df = df[["CD_MUN","NM_MUN"]].dropna().drop_duplicates().sort_values(["NM_MUN","CD_MUN"])
    mun_options = [None] + mun_df["CD_MUN"].tolist()
    name_map = dict(zip(mun_df["CD_MUN"], mun_df["NM_MUN"]))
    sel_mun = st.selectbox("Município", options=mun_options, format_func=lambda c: "— selecione —" if c is None else f"{c} — {name_map.get(c,'')}")
    if sel_mun is None:
        st.stop()
    df_mun = df[df["CD_MUN"] == sel_mun]
else:
    st.error("Colunas CD_MUN/NM_MUN ausentes na base.")
    st.stop()

cols_show = [c for c in ["CD_SETOR","SITUACAO","CD_SITUACAO","SITUACAO_DET_TXT","CD_TIPO","TP_SETOR_TXT","AREA_KM2"] if c in df_mun.columns]
st.dataframe(df_mun[cols_show].drop_duplicates().sort_values("CD_SETOR"), use_container_width=True, height=650)
