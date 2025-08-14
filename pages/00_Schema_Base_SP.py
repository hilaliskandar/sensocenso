import sys
from pathlib import Path as _P
import streamlit as st
import pandas as pd

SRC = _P(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from censo_app.transform import load_sp_age_sex_enriched

st.set_page_config(layout="wide")
st.title("📑 Schema da Base (SP) — tipos e disponibilidade")

def _norm(s: str) -> str:
    return (s or "").strip().strip('"').strip("'").replace("\\", "/")

parquet_path = st.text_input("Parquet (SP)", r"D:\\repo\\saida_parquet\\base_integrada_final.parquet", key="schema_path")
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

dtypes = df.dtypes.astype(str).rename("dtype").reset_index().rename(columns={"index":"coluna"})
non_null = df.notna().sum().rename("non_null").reset_index().rename(columns={"index":"coluna"})
nulls = df.isna().sum().rename("nulls").reset_index().rename(columns={"index":"coluna"})
nunique = df.nunique(dropna=True).rename("nunique").reset_index().rename(columns={"index":"coluna"})

schema = dtypes.merge(non_null, on="coluna").merge(nulls, on="coluna").merge(nunique, on="coluna")
schema = schema.sort_values("coluna").reset_index(drop=True)

st.dataframe(schema, use_container_width=True, height=600)

keys = ["CD_SETOR","SITUACAO","CD_SITUACAO","SITUACAO_DET_TXT","CD_TIPO","TP_SETOR_TXT","CD_MUN","NM_MUN","CD_UF","NM_UF"]
present = {k: (k in df.columns) for k in keys}
st.write("**Presença das chaves principais:**", present)
