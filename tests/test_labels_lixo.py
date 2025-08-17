import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from censo_app.labels import strip_known_boilerplate, apply_simplify_and_wrap
import pandas as pd


def test_strip_known_boilerplate_lixo_prefix():
    s = "Destinação do lixo do domicílio é Coletado diretamente"
    assert strip_known_boilerplate(s) == "Coletado diretamente"


def test_apply_simplify_and_wrap_dominant_prefix_and_wrap():
    df = pd.DataFrame({
        "categoria": [
            "Domicílios Particulares Permanentes Ocupados, Destinação do lixo do domicílio é Coletado diretamente",
            "Domicílios Particulares Permanentes Ocupados, Destinação do lixo do domicílio é Queimado no domicílio",
        ],
        "valor": [60, 40],
    })
    out = apply_simplify_and_wrap(df, title="Destinação do lixo do domicílio")
    assert all(x in out.columns for x in ["categoria_simplificada", "categoria_wrapped"]) 
    # Ensure prefix is removed and lines are shortish
    assert out.loc[0, "categoria_simplificada"].startswith("Coletado")
    assert out.loc[1, "categoria_simplificada"].startswith("Queimado")
    assert "<br>" in out.loc[1, "categoria_wrapped"] or len(out.loc[1, "categoria_wrapped"]) <= 18
