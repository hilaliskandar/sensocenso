import sys
from pathlib import Path
import streamlit as st

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

st.set_page_config(page_title="Censo 2022 — SP (v1.9.2)", layout="wide")
st.title("Censo 2022 — Plataforma SP (v1.9.2)")
st.write("Abra a página **02_Piramide_Etaria** no menu lateral.")
