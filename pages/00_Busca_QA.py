
import streamlit as st
from pathlib import Path

st.title("🔎 Busca & QA (Haystack)")
st.info("Para habilitar, instale: haystack-ai, sentence-transformers e faiss-cpu e adicione textos em docs/.")
st.code("pip install haystack-ai sentence-transformers faiss-cpu", language="bash")
st.write("Este MVP inclui o esqueleto para integrar Haystack 2.x em src/censo_app/haystack_qa.py.")
