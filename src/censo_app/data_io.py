
from __future__ import annotations
import pandas as pd
from pathlib import Path
import streamlit as st

@st.cache_data(show_spinner=False)
def load_local_pyramid(csv_path: str | Path) -> pd.DataFrame:
    p = Path(csv_path)
    if not p.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {p}")
    df = pd.read_csv(p)
    rename = {
        "idade": "idade_grupo",
        "grupo_idade": "idade_grupo",
        "sexo_cat": "sexo",
        "quantidade": "valor",
        "populacao": "valor",
    }
    df = df.rename(columns={k:v for k,v in rename.items() if k in df.columns})
    cols = ["idade_grupo","sexo","valor"]
    for c in cols:
        if c not in df.columns:
            raise ValueError(f"CSV precisa conter coluna '{c}'")
    for c in ["cod","nome"]:
        if c not in df.columns:
            df[c] = None
    return df
