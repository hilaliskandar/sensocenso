
import streamlit as st

st.set_page_config(page_title="Censo 2022 — Plataforma", layout="wide")
st.title("Censo 2022 — Plataforma de Análise")
st.write(
    "Explore dados demográficos do Censo 2022 e construa pirâmides etárias. "
    "Use as páginas na barra lateral."
)

st.markdown(
    """
    **Páginas:**
    - **00_Busca_QA**: RAG/Haystack sobre notas e documentação.
    - **01_Piramide_Etaria**: Visualize pirâmides etárias por Brasil/UF/Município (arquivo local ou SIDRA).
    """
)
