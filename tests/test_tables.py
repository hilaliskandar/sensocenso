"""Tests for src/censo_app/tables.py"""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from censo_app.tables import build_abnt_demographic_table, render_abnt_html

AGE_ORDER = [
    "0 a 4 anos", "5 a 9 anos", "10 a 14 anos", "15 a 19 anos",
    "20 a 24 anos", "25 a 29 anos", "30 a 39 anos", "40 a 49 anos",
    "50 a 59 anos", "60 a 69 anos", "70 anos ou mais",
]


def _make_plot_df():
    rows = []
    for faixa in AGE_ORDER:
        rows.append({"faixa_etaria": faixa, "sexo": "Masculino", "populacao": 100})
        rows.append({"faixa_etaria": faixa, "sexo": "Feminino",  "populacao": 80})
    return pd.DataFrame(rows)


# --- build_abnt_demographic_table ---

def test_build_abnt_table_structure():
    df = _make_plot_df()
    result = build_abnt_demographic_table(df, AGE_ORDER)
    expected_cols = {"Faixa Etária", "Masculino", "Feminino", "Total", "% Masculino", "% Feminino"}
    assert expected_cols <= set(result.columns)


def test_build_abnt_table_has_total_row():
    df = _make_plot_df()
    result = build_abnt_demographic_table(df, AGE_ORDER)
    assert "TOTAL" in result["Faixa Etária"].values


def test_build_abnt_table_total_sum():
    df = _make_plot_df()
    result = build_abnt_demographic_table(df, AGE_ORDER)
    total_row = result[result["Faixa Etária"] == "TOTAL"].iloc[0]
    # 11 faixas × 100 Masculino = 1100; 11 × 80 Feminino = 880; Total = 1980
    assert total_row["Masculino"] == 1100
    assert total_row["Feminino"] == 880
    assert total_row["Total"] == 1980


def test_build_abnt_table_percentages():
    df = _make_plot_df()
    result = build_abnt_demographic_table(df, AGE_ORDER)
    faixa_row = result[result["Faixa Etária"] == "0 a 4 anos"].iloc[0]
    # 100/(100+80) ≈ 55.6%
    assert abs(faixa_row["% Masculino"] - 55.6) < 0.2
    assert abs(faixa_row["% Feminino"] - 44.4) < 0.2


def test_build_abnt_table_empty_returns_gracefully():
    df = pd.DataFrame({"faixa_etaria": [], "sexo": [], "populacao": []})
    result = build_abnt_demographic_table(df, AGE_ORDER)
    assert isinstance(result, pd.DataFrame)


# --- render_abnt_html ---

def test_render_abnt_html_produces_table_tag():
    df = _make_plot_df()
    table = build_abnt_demographic_table(df, AGE_ORDER)
    html = render_abnt_html(table)
    assert "<table" in html
    assert "</table>" in html
    assert "abnt" in html


def test_render_abnt_html_with_delta_column():
    df = _make_plot_df()
    table = build_abnt_demographic_table(df, AGE_ORDER)
    table["Δ vs Comp."] = 1.5
    html = render_abnt_html(table)
    assert "▲" in html


def test_render_abnt_html_delta_zero():
    df = _make_plot_df()
    table = build_abnt_demographic_table(df, AGE_ORDER)
    table["Δ vs Comp."] = 0.0
    html = render_abnt_html(table)
    assert "—" in html
