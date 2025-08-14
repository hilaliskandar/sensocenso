
import streamlit as st

# === Bootstrapping de imports (robusto) ===
import sys
from pathlib import Path as _Path

def _find_and_add_src(anchor: _Path, levels: int = 6):
    # Adiciona a pasta 'src' mais próxima ao sys.path, subindo até 'levels' níveis.
    for i in range(levels + 1):
        base = anchor if i == 0 else anchor.parents[i-1]
        cand = base / "src"
        if cand.exists() and (cand / "censo_app").exists():
            if str(cand) not in sys.path:
                sys.path.insert(0, str(cand))
            if str(base) not in sys.path:
                sys.path.insert(0, str(base))
            return cand
    return None

_THIS = _Path(__file__).resolve()
_src = _find_and_add_src(_THIS.parent, levels=6)
if _src is None:
    _src = _find_and_add_src(_Path.cwd(), levels=6)

import pandas as pd

try:
    from censo_app.data_io import load_local_pyramid
    from censo_app.sidra import get_age_sex_groups
    from censo_app.viz import make_age_pyramid
except ModuleNotFoundError:
    from src.censo_app.data_io import load_local_pyramid
    from src.censo_app.sidra import get_age_sex_groups
    from src.censo_app.viz import make_age_pyramid

st.title("👶👵 Pirâmide Etária — Censo 2022 (arquivo/SIDRA)")
fonte = st.radio("Fonte de dados", ["Arquivo local", "SIDRA (API)"], horizontal=True)
col1, col2, col3 = st.columns([1,1,2], vertical_alignment="bottom")
nivel = col1.selectbox("Nível geográfico", ["BR","UF","MU"], index=0)
if fonte == "Arquivo local":
    csv_path = col2.text_input("Caminho do CSV", "data/piramide_exemplo.csv")
    df = load_local_pyramid(csv_path)
    st.success(f"{len(df):,} linhas carregadas do arquivo.")
else:
    tabela = col2.text_input("Tabela SIDRA (ex.: 1209, 475, 200)", "1209")
    codigo = col3.text_input("Código(s) do local (ex.: all, 33, 3550308)", "all")
    try:
        table_id = int(tabela)
    except:
        st.error("Informe um número de tabela válido.")
        st.stop()
    with st.spinner("Consultando SIDRA..."):
        df = get_age_sex_groups(table_id=table_id, periodo="2022", nivel=nivel, local=codigo)
    if df.empty:
        st.warning("Nenhum dado retornado.")
        st.stop()
if "nome" in df.columns:
    locais = sorted(df["nome"].dropna().unique().tolist())
    if locais:
        alvo = st.selectbox("Selecione o local", ["<primeiro>"] + locais, index=0)
        if alvo != "<primeiro>":
            df = df[df["nome"] == alvo]
if "idade_grupo" not in df.columns:
    for c in ["D3N","D4N"]:
        if c in df.columns:
            df = df.rename(columns={c:"idade_grupo"})
            break
if "sexo" not in df.columns:
    df["sexo"] = "Total"
st.dataframe(df.head(50))
df_plot = df.groupby(["idade_grupo","sexo"], as_index=False)["valor"].sum()
fig = make_age_pyramid(df_plot, title="Pirâmide etária — Censo 2022")
st.plotly_chart(fig, use_container_width=True)
