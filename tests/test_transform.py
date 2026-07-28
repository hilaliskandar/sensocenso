"""Tests for non-IO parts of src/censo_app/transform.py"""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from censo_app.transform import (
    _normcol,
    _rename_by_alias,
    _normalize_codes,
    _ensure_decodes,
    _derive_macro_from_cd,
    wide_to_long_pyramid,
    aggregate_pyramid,
    get_variable_label,
    AGE_GROUPS,
)


# --- _normcol ---

def test_normcol_removes_accents():
    result = _normcol("situação")
    assert result == "SITUACAO"


def test_normcol_replaces_spaces():
    result = _normcol("nome do município")
    assert result == "NOME_DO_MUNICIPIO"


def test_normcol_uppercase():
    assert _normcol("cd_mun") == "CD_MUN"


# --- _rename_by_alias ---

def test_rename_by_alias_basic():
    df = pd.DataFrame({"CODIGO_DO_MUNICIPIO": [1], "V0001": [100]})
    result = _rename_by_alias(df)
    assert "CD_MUN" in result.columns


def test_rename_by_alias_v_codes():
    df = pd.DataFrame({"v0001": [10], "v0007": [20]})
    result = _rename_by_alias(df)
    assert "V0001" in result.columns
    assert "V0007" in result.columns


# --- _normalize_codes ---

def test_normalize_codes_strips_letters():
    df = pd.DataFrame({"CD_SETOR": ["35001A"]})
    result = _normalize_codes(df)
    assert result["CD_SETOR"].iloc[0] == "35001"


# --- _ensure_decodes ---

def test_ensure_decodes_situacao_from_cd():
    df = pd.DataFrame({"CD_SITUACAO": [1, 8]})
    result = _ensure_decodes(df)
    assert "SITUACAO" in result.columns
    assert result["SITUACAO"].iloc[0] == "Urbana"
    assert result["SITUACAO"].iloc[1] == "Rural"


def test_ensure_decodes_tipo_from_cd():
    df = pd.DataFrame({"CD_TIPO": [0, 1]})
    result = _ensure_decodes(df)
    assert "TP_SETOR_TXT" in result.columns
    assert result["TP_SETOR_TXT"].iloc[0] == "Não especial"
    assert "Favela" in result["TP_SETOR_TXT"].iloc[1]


# --- _derive_macro_from_cd ---

def test_derive_macro_urban():
    assert _derive_macro_from_cd(1) == "Urbana"
    assert _derive_macro_from_cd(2) == "Urbana"
    assert _derive_macro_from_cd(3) == "Urbana"


def test_derive_macro_rural():
    assert _derive_macro_from_cd(5) == "Rural"
    assert _derive_macro_from_cd(8) == "Rural"


def test_derive_macro_invalid():
    assert _derive_macro_from_cd("x") is None


# --- get_variable_label ---

def test_get_variable_label():
    label = get_variable_label("V0001")
    assert label is not None
    assert "Total" in label or "pessoas" in label.lower()


def test_get_variable_label_lowercase():
    assert get_variable_label("v0001") == get_variable_label("V0001")


def test_get_variable_label_unknown():
    assert get_variable_label("V9999") is None


# --- wide_to_long_pyramid ---

def _make_wide_df():
    """Create a minimal wide DataFrame with 22 age columns."""
    data = {"CD_MUN": ["3500105"], "NM_MUN": ["Adamantina"], "CD_SITUACAO": [1], "V0001": [1000]}
    for grp in AGE_GROUPS:
        data[f"Sexo masculino, {grp}"] = [50]
        data[f"Sexo feminino, {grp}"] = [40]
    return pd.DataFrame(data)


def test_wide_to_long_row_count():
    df = _make_wide_df()
    result = wide_to_long_pyramid(df)
    # 1 row × 22 cols → 22 long rows
    assert len(result) == 22


def test_wide_to_long_columns():
    df = _make_wide_df()
    result = wide_to_long_pyramid(df)
    assert "idade_grupo" in result.columns
    assert "sexo" in result.columns
    assert "valor" in result.columns


def test_wide_to_long_sexo_values():
    df = _make_wide_df()
    result = wide_to_long_pyramid(df)
    sexos = set(result["sexo"].unique())
    assert sexos == {"Masculino", "Feminino"}


def test_wide_to_long_raises_on_missing_age_cols():
    df = pd.DataFrame({"CD_MUN": [1], "V0001": [100]})
    with pytest.raises(ValueError, match="etárias"):
        wide_to_long_pyramid(df)


# --- aggregate_pyramid ---

def test_aggregate_pyramid_sum():
    df = _make_wide_df()
    long = wide_to_long_pyramid(df)
    result = aggregate_pyramid(long)
    # Should aggregate to 11 faixas × 2 sexos = 22 rows
    assert len(result) == 22
    masc = result[(result["sexo"] == "Masculino") & (result["idade_grupo"] == AGE_GROUPS[0])]
    assert masc["valor"].iloc[0] == 50
