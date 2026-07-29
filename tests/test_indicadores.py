"""Tests for src/censo_app/indicadores_demograficos.py"""
import sys
import math
from pathlib import Path

import pandas as pd
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from censo_app.indicadores_demograficos import (
    calcular_populacoes_agrupadas,
    calcular_indicadores_demograficos,
    gerar_flags_qualidade,
    calcular_age_heaping_index,
)


def _make_df(ages_pops: list[tuple[int, int]]) -> pd.DataFrame:
    """Create a minimal long DataFrame with (idade, pop) pairs, sexo=Total."""
    rows = [{"idade": a, "pop": p, "sexo": "Total"} for a, p in ages_pops]
    return pd.DataFrame(rows)


# --- calcular_populacoes_agrupadas ---

def test_grupos_basic():
    df = _make_df([(5, 100), (30, 200), (70, 50)])
    g = calcular_populacoes_agrupadas(df)
    assert g["pop_total"] == 350
    assert g["pop_0_14"] == 100
    assert g["pop_15_64"] == 200
    assert g["pop_65p"] == 50


def test_grupos_empty():
    df = pd.DataFrame({"idade": [], "pop": [], "sexo": []})
    g = calcular_populacoes_agrupadas(df)
    assert g["pop_total"] == 0


# --- calcular_indicadores_demograficos ---

def test_rdt_formula():
    grupos = {
        "pop_0_14": 300, "pop_15_64": 500, "pop_20_64": 480,
        "pop_60p": 100, "pop_65p": 80, "pop_80p": 10,
        "pop_total": 880, "pop_idade0": 8,
    }
    ind = calcular_indicadores_demograficos(grupos)
    expected_rdt = (300 + 80) / 500 * 100
    assert abs(ind["RDT"] - expected_rdt) < 0.01


def test_rdt_zero_denominator():
    grupos = {
        "pop_0_14": 100, "pop_15_64": 0, "pop_20_64": 0,
        "pop_60p": 10, "pop_65p": 5, "pop_80p": 1,
        "pop_total": 105, "pop_idade0": 2,
    }
    ind = calcular_indicadores_demograficos(grupos)
    assert math.isnan(ind["RDT"])
    assert math.isnan(ind["RDJ"])


def test_ie_60p():
    grupos = {
        "pop_0_14": 200, "pop_15_64": 400, "pop_20_64": 380,
        "pop_60p": 100, "pop_65p": 60, "pop_80p": 10,
        "pop_total": 700, "pop_idade0": 5,
    }
    ind = calcular_indicadores_demograficos(grupos)
    assert abs(ind["IE_60p"] - 100 / 200 * 100) < 0.01


# --- gerar_flags_qualidade ---

def test_flag_denominador_pequeno():
    grupos = {"pop_15_64": 499, "pop_total": 600, "pop_0_14": 50, "pop_65p": 40,
              "pop_80p": 5, "pop_idade0": 3, "pop_60p": 60}
    flags = gerar_flags_qualidade(grupos)
    assert flags["denominador_pequeno"] is True


def test_flag_denominador_grande():
    grupos = {"pop_15_64": 500, "pop_total": 700, "pop_0_14": 100, "pop_65p": 80,
              "pop_80p": 10, "pop_idade0": 5, "pop_60p": 90}
    flags = gerar_flags_qualidade(grupos)
    assert flags["denominador_pequeno"] is False


def test_flag_idosos_dominantes():
    grupos = {"pop_15_64": 500, "pop_total": 700, "pop_0_14": 50, "pop_65p": 100,
              "pop_80p": 20, "pop_idade0": 2, "pop_60p": 120}
    flags = gerar_flags_qualidade(grupos)
    assert flags["idosos_dominantes"] is True


def test_flag_zero_total():
    grupos = {"pop_15_64": 0, "pop_total": 0, "pop_0_14": 0, "pop_65p": 0,
              "pop_80p": 0, "pop_idade0": 0, "pop_60p": 0}
    flags = gerar_flags_qualidade(grupos)
    assert flags["zero_total"] is True


def test_flag_age_heaping_severe():
    grupos = {"pop_15_64": 600, "pop_total": 800, "pop_0_14": 100, "pop_65p": 50,
              "pop_80p": 5, "pop_idade0": 6, "pop_60p": 60}
    flags = gerar_flags_qualidade(grupos, whipple_index=200.0)
    assert flags["age_heaping"] is True
    assert flags["age_heaping_moderado"] is False


def test_flag_age_heaping_moderate():
    grupos = {"pop_15_64": 600, "pop_total": 800, "pop_0_14": 100, "pop_65p": 50,
              "pop_80p": 5, "pop_idade0": 6, "pop_60p": 60}
    flags = gerar_flags_qualidade(grupos, whipple_index=130.0)
    assert flags["age_heaping"] is False
    assert flags["age_heaping_moderado"] is True


def test_flag_age_heaping_good():
    grupos = {"pop_15_64": 600, "pop_total": 800, "pop_0_14": 100, "pop_65p": 50,
              "pop_80p": 5, "pop_idade0": 6, "pop_60p": 60}
    flags = gerar_flags_qualidade(grupos, whipple_index=95.0)
    assert flags["age_heaping"] is False
    assert flags["age_heaping_moderado"] is False


# --- calcular_age_heaping_index ---

def test_whipple_perfect_distribution():
    # Uniform distribution: all ages from 23 to 62 have equal population
    rows = [{"idade": a, "pop": 100, "sexo": "Total"} for a in range(23, 63)]
    df = pd.DataFrame(rows)
    wi = calcular_age_heaping_index(df)
    # Whipple should be ~100 for uniform data
    assert 80 < wi < 120


def test_whipple_extreme_heaping():
    # Only ages ending in 0 and 5 have population → extreme heaping
    rows = []
    for a in range(23, 63):
        pop = 1000 if a % 5 == 0 else 1
        rows.append({"idade": a, "pop": pop, "sexo": "Total"})
    df = pd.DataFrame(rows)
    wi = calcular_age_heaping_index(df)
    assert wi > 174


def test_whipple_empty():
    df = pd.DataFrame({"idade": [], "pop": [], "sexo": []})
    wi = calcular_age_heaping_index(df)
    assert math.isnan(wi)
