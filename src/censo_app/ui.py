from __future__ import annotations
from pathlib import Path as _P
import base64
import streamlit as st


def _root_dir() -> _P:
    # src/censo_app/ui.py -> ../../.. (app root)
    # ui.py -> censo_app -> src -> sensocenso (root)
    return _P(__file__).resolve().parents[3]


def _load_logo_b64() -> str | None:
    root = _root_dir()
    png_path = root / "assets" / "logo.png"
    if png_path.exists():
        try:
            return base64.b64encode(png_path.read_bytes()).decode("ascii")
        except Exception:
            pass
    # optional fallback: raw base64 string in assets/logo_base64.txt
    b64_path = root / "assets" / "logo_base64.txt"
    if b64_path.exists():
        try:
            return (b64_path.read_text(encoding="utf-8").strip()) or None
        except Exception:
            return None
    return None


def render_topbar(title: str = "Senso&Censo — Explorador de dados censitários", subtitle: str = "Censo 2022 — SP") -> None:
    """Renderiza uma barra superior com o logo do projeto, se disponível.

    Busca o arquivo em assets/logo.png na raiz do app. Se não existir,
    tenta ler uma string Base64 de assets/logo_base64.txt.
    """
    st.markdown(
        '''
        <style>
        [data-testid="stSidebar"] {background: #c1121f !important;}
        [data-testid="stSidebar"] * {color: #fff !important;}
        .stApp { background-color: #f5f6f7; }
        .block-container { padding-top: 0.5rem; }
        .senso-topbar { background:#000; color:#fff; padding:10px 16px; margin:0 0 10px 0; border-radius:10px; display:flex; align-items:center; gap:12px; }
        .senso-title { font-size: 1.1rem; font-weight: 600; line-height:1.2; }
        .senso-sub { font-size: 0.85rem; opacity: 0.8; }
        </style>
        ''',
        unsafe_allow_html=True,
    )

    b64 = _load_logo_b64()
    if b64:
        html = (
            f"""
            <div class='senso-topbar'>
                <img src='data:image/png;base64,{b64}' height='42' />
                <div>
                  <div class='senso-title'>{title}</div>
                  <div class='senso-sub'>{subtitle}</div>
                </div>
            </div>
            """
        )
        st.markdown(html, unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='senso-topbar'><b>{title}</b></div>", unsafe_allow_html=True)
