"""Tests for src/censo_app/formatting.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from censo_app.formatting import fmt_br


def test_fmt_br_integer():
    assert fmt_br(1000) == "1.000"
    assert fmt_br(1000000) == "1.000.000"
    assert fmt_br(0) == "0"


def test_fmt_br_float():
    result = fmt_br(1234.5, decimals=1)
    assert result == "1.234,5"


def test_fmt_br_none():
    assert fmt_br(None) == ""


def test_fmt_br_nan():
    import math
    assert fmt_br(float("nan")) == ""


def test_fmt_br_negative():
    result = fmt_br(-500)
    assert "-" in result
    assert "500" in result


def test_fmt_br_small():
    assert fmt_br(5, decimals=2) == "5,00"
