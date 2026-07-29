"""Tests for src/censo_app/text_utils.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from censo_app.text_utils import clean_label, sanitize_title, wrap_title


# --- clean_label ---

def test_clean_label_normal():
    assert clean_label("São Paulo") == "São Paulo"


def test_clean_label_empty():
    assert clean_label("") is None
    assert clean_label("  ") is None


def test_clean_label_nan_variants():
    for val in ("nan", "NaN", "None", "undefined", "null", "-", "—"):
        assert clean_label(val) is None, f"Expected None for {val!r}"


def test_clean_label_strips_whitespace():
    result = clean_label("  hello  ")
    assert result == "hello"


def test_clean_label_non_string():
    # Numeric values should be converted to string and returned
    result = clean_label(42)
    assert result == "42"


# --- sanitize_title ---

def test_sanitize_title_normal():
    assert sanitize_title("São Paulo") == "São Paulo"


def test_sanitize_title_empty():
    result = sanitize_title("")
    assert result == "Estado de São Paulo"


def test_sanitize_title_none():
    result = sanitize_title(None)
    assert result == "Estado de São Paulo"


def test_sanitize_title_nan():
    result = sanitize_title("nan")
    assert result == "Estado de São Paulo"


def test_sanitize_title_trailing_separator():
    result = sanitize_title("Município — ")
    assert result == "Estado de São Paulo"


# --- wrap_title ---

def test_wrap_title_short():
    result = wrap_title("SP", width=42)
    assert result == "SP"


def test_wrap_title_long():
    long = "Este é um título muito longo que precisa ser quebrado em várias linhas para caber no gráfico"
    result = wrap_title(long, width=20)
    assert "<br>" in result


def test_wrap_title_no_break_needed():
    result = wrap_title("Olá", width=100)
    assert "<br>" not in result
