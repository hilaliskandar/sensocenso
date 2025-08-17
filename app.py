import sys
from pathlib import Path as _P
import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

# Ensure local package import
SRC = _P(__file__).resolve().parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from censo_app.ui import render_topbar

# App setup: wide layout with collapsed sidebar by default
st.set_page_config(page_title="Explorador de Dados Censitários", layout="wide", initial_sidebar_state="collapsed")

# Top bar
render_topbar(title="Explorador de Dados Censitários", subtitle="Censo 2022 — SP")

# Minimal CSS: compact margins and better wrapping for long labels/titles
st.markdown(
    """
    <style>
      .block-container { padding-left: 0.75rem !important; padding-right: 0.75rem !important; max-width: 100% !important; }
      .block-container h1, .block-container h2, .block-container h3, .block-container h4 {
        white-space: normal !important; overflow-wrap: anywhere; word-break: break-word;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# Sidebar: keepalive toggle and quick navigation links
with st.sidebar:
    keepalive = st.checkbox("Evitar expirar (autorefresh a cada 5 min)", value=False)
    if keepalive and st_autorefresh:
        st_autorefresh(interval=5*60*1000, key="keepalive")
    elif keepalive:
        st.info("Para ativar: pip install streamlit-autorefresh")

    st.markdown("---")
    st.caption("Navegação")
    try:
        st.page_link("app.py", label="Início", icon="🏠")
        st.page_link("pages/10_Demografia.py", label="Demografia", icon="🏛️")
        # 'Sobre' é opcional; será exibido apenas se existir
        st.page_link("pages/99_Sobre.py", label="Sobre", icon="ℹ️")
    except Exception:
        pass

# Landing content (no data loading here to avoid duplicating Demografia)
st.title("Bem-vindo(a)")
st.write(
    "Esta é a página inicial do Explorador de Dados Censitários para o Censo 2022 em SP."
)

st.markdown(
    "- Acesse a seção Demografia para pirâmides etárias e tabelas formatadas.\n"
    "- Use os filtros dentro da página Demografia para Situação (Urbana/Rural), Tipo de Setor e recortes territoriais."
)

col1, col2 = st.columns([1,1])
with col1:
    st.page_link("pages/10_Demografia.py", label="Ir para Demografia", icon="➡️")
with col2:
    try:
        st.page_link("pages/99_Sobre.py", label="Sobre o projeto", icon="📄")
    except Exception:
        pass

st.divider()
st.caption("Fonte: Censo 2022 — IBGE")
