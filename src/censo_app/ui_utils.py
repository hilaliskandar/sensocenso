from __future__ import annotations

from typing import Iterable, Mapping, Optional

import pandas as pd
import streamlit as st


_ABNT_CSS_KEY = "__abnt_css_loaded__"


def ensure_abnt_css(height_caption_px: int = 64) -> None:
    """Injects ABNT-like CSS once per session for figure captions and sources."""
    if st.session_state.get(_ABNT_CSS_KEY):
        return
    st.markdown(
        f"""
        <style>
        .abnt-figure {{ max-width: 100%; margin: 0.25rem 0 0.25rem 0; }}
        .abnt-caption {{
            text-align: center;
            font-weight: 700;
            font-size: 11pt;
            line-height: 1.2;
            height: {height_caption_px}px;
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 4px 8px;
            white-space: normal;
            word-break: break-word;
            overflow-wrap: anywhere;
        }}
        .abnt-source {{ font-size: 10pt; text-align: left; margin-top: 6px; }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state[_ABNT_CSS_KEY] = True


def render_abnt_caption(text: str) -> None:
    st.markdown(
        f"<div class='abnt-figure'><div class='abnt-caption'><strong>{text}</strong></div></div>",
        unsafe_allow_html=True,
    )


def render_abnt_source(text: str) -> None:
    st.markdown(
        f"<div class='abnt-figure'><div class='abnt-source'>{text}</div></div>",
        unsafe_allow_html=True,
    )


def dataframe_to_csv_download(
    df: pd.DataFrame,
    file_name: str,
    label: str = "Baixar CSV",
    columns: Optional[Iterable[str]] = None,
    rename: Optional[Mapping[str, str]] = None,
) -> None:
    """Expose a DataFrame as CSV download button with UTF-8 BOM.

    - columns: optional subset/order of columns to include
    - rename: optional column rename mapping applied before selecting columns
    """
    data = df.copy()
    if rename:
        data = data.rename(columns=dict(rename))
    if columns:
        cols = [c for c in columns if c in data.columns]
        data = data[cols]
    csv_bytes = data.to_csv(index=False).encode("utf-8-sig")
    st.download_button(label, data=csv_bytes, file_name=file_name, mime="text/csv")
