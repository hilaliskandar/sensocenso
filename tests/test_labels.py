import sys
from pathlib import Path

# Ensure 'src' is on sys.path
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd
from censo_app.labels import strip_known_boilerplate, apply_simplify_and_wrap


def test_strip_known_boilerplate_esgoto_inexistente():
    s = (
        "Domicílios Particulares Permanentes Ocupados, Destinação do esgoto inexistente, "
        "pois não tinham banheiro nem sanitário."
    )
    assert strip_known_boilerplate(s) == "sem banheiro nem sanitário"


def test_strip_known_boilerplate_banheiros_regex():
    s = (
        "9+ banheiros de uso exclusivo com chuveiro e vaso sanitário existentes no domicílio"
    )
    assert strip_known_boilerplate(s) == "9+"


def test_apply_simplify_and_wrap_removes_title_prefix_and_wraps():
    df = pd.DataFrame(
        {
            "categoria": [
                "Domicílios Particulares Permanentes Ocupados, Destinação do esgoto do banheiro ou sanitário ou buraco para dejeções é Rede geral de esgoto ou pluvial",
            ],
            "valor": [100],
        }
    )
    out = apply_simplify_and_wrap(df, title="Destinação do esgoto do banheiro ou sanitário")
    assert "categoria_simplificada" in out.columns
    # Should not include the long prefix
    assert not out.loc[0, "categoria_simplificada"].lower().startswith("domicílios particulares")
    # Wrapped variant exists
    assert "categoria_wrapped" in out.columns
