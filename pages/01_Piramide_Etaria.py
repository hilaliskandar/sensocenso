
import streamlit as st
import pandas as pd
from src.censo_app.data_io import load_local_pyramid
from src.censo_app.sidra import get_age_sex_groups
from src.censo_app.viz import make_age_pyramid

st.title("👶👵 Pirâmide Etária — Censo 2022")

fonte = st.radio("Fonte de dados", ["Arquivo local", "SIDRA (API)"], horizontal=True)

col1, col2, col3 = st.columns([1,1,2], vertical_alignment="bottom")
nivel = col1.selectbox("Nível geográfico", ["BR","UF","MU"], index=0, help="BR=Brasil, UF=Estado, MU=Município")
if fonte == "Arquivo local":
    csv_path = col2.text_input("Caminho do CSV", "data/piramide_exemplo.csv")
    codigo = None
    tabela = None
else:
    tabela = col2.text_input("Tabela SIDRA (ex.: 1209, 475, 200)", "1209")
    codigo = col3.text_input("Código(s) do local (ex.: all, 33, 3550308)", "all")

if fonte == "Arquivo local":
    df = load_local_pyramid(csv_path)
    st.success(f"{len(df):,} linhas carregadas do arquivo.")
else:
    try:
        table_id = int(tabela)
    except:
        st.error("Informe um número de tabela válido.")
        st.stop()
    with st.spinner("Consultando SIDRA..."):
        df = get_age_sex_groups(table_id=table_id, periodo="2022", nivel=nivel, local=codigo)
    if df.empty:
        st.warning("Nenhum dado retornado pela API. Tente outra tabela ou verifique os parâmetros.")
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
