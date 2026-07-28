"""Tests for src/censo_app/demog_utils.py"""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from censo_app.demog_utils import normalize_age_label, pad_pyramid_categories, aggregate_sex_age

AGE_ORDER = [
    "0 a 4 anos", "5 a 9 anos", "10 a 14 anos", "15 a 19 anos",
    "20 a 24 anos", "25 a 29 anos", "30 a 39 anos", "40 a 49 anos",
    "50 a 59 anos", "60 a 69 anos", "70 anos ou mais",
]


# --- normalize_age_label ---

def test_normalize_age_label_dash():
    assert normalize_age_label("0-4 anos") == "0 a 4 anos"
    assert normalize_age_label("15-19") == "15 a 19 anos"


def test_normalize_age_label_plus():
    assert normalize_age_label("70+") == "70 anos ou mais"
    assert normalize_age_label("70 anos ou mais") == "70 anos ou mais"


def test_normalize_age_label_whitespace():
    assert normalize_age_label("  30 a 39 anos  ") == "30 a 39 anos"


def test_normalize_age_label_em_dash():
    # En-dash / em-dash should be normalized to 'a'
    result = normalize_age_label("10–14 anos")
    assert "10" in result and "14" in result


# --- pad_pyramid_categories ---

def _make_df(rows):
    return pd.DataFrame(rows, columns=["sexo", "faixa_etaria", "populacao"])


def test_pad_pyramid_categories_completes_missing():
    df = _make_df([
        ("Masculino", "0 a 4 anos", 100),
        ("Feminino",  "0 a 4 anos", 90),
    ])
    result = pad_pyramid_categories(df, AGE_ORDER)
    # Should have 11 faixas × 2 sexos = 22 rows
    assert len(result) == 22
    # Missing faixas filled with 0
    missing = result[(result["faixa_etaria"] == "70 anos ou mais") & (result["sexo"] == "Masculino")]
    assert missing["populacao"].iloc[0] == 0


def test_pad_pyramid_categories_both_sexes_present():
    df = _make_df([(s, f, 50) for s in ("Masculino", "Feminino") for f in AGE_ORDER])
    result = pad_pyramid_categories(df, AGE_ORDER)
    assert len(result) == 22
    assert (result["populacao"] == 50).all()


# --- aggregate_sex_age ---

def test_aggregate_sex_age_sums():
    df = pd.DataFrame({
        "sexo": ["Masculino", "Masculino", "Feminino"],
        "faixa_etaria": ["0 a 4 anos", "0 a 4 anos", "0 a 4 anos"],
        "populacao": [100, 50, 80],
    })
    result = aggregate_sex_age(df)
    masc = result[(result["sexo"] == "Masculino") & (result["faixa_etaria"] == "0 a 4 anos")]
    assert masc["populacao"].iloc[0] == 150


def test_aggregate_sex_age_columns():
    df = pd.DataFrame({
        "sexo": ["Masculino"],
        "faixa_etaria": ["5 a 9 anos"],
        "populacao": [200],
    })
    result = aggregate_sex_age(df)
    assert set(result.columns) >= {"sexo", "faixa_etaria", "populacao"}
