from __future__ import annotations

import pandas as pd
import pytest

from tic_tim_demografia.etapa04 import _agregar_municipios, _converter_coluna, _derivar_setores


def _demografia() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "codigo_setor": ["350000005000001", "350000005000002", "350000005000003"],
            "codigo_ibge": ["3500000"] * 3,
            "V01006": ["100", "200", "50"],
            "V01008": ["52", "104", "26"],
            "V01023": ["5", "10", "x"],
            "V01024": ["5", "10", "2"],
            "V01025": ["5", "10", "2"],
            "V01026": ["10", "20", "4"],
            "V01027": ["5", "10", "2"],
            "V01031": ["4", "10", "2"],
        }
    )


def test_converter_coluna_preserva_sigilo_e_rejeita_simbolo_desconhecido() -> None:
    serie = _converter_coluna(pd.Series(["1", "x", "X", None]), "teste")
    assert serie.iloc[0] == 1
    assert serie.iloc[1:].isna().all()
    with pytest.raises(ValueError):
        _converter_coluna(pd.Series(["1", ".."]), "teste")


def test_derivacao_complete_case_nao_transforma_sigilo_em_zero() -> None:
    universo = pd.DataFrame(
        {
            "codigo_setor": ["350000005000001", "350000005000002", "350000005000003"],
            "codigo_ibge": ["3500000"] * 3,
        }
    )
    out = _derivar_setores(universo, _demografia())
    assert out["valido_m1549"].tolist() == [True, True, False]
    assert out["valido_cwr"].tolist() == [True, True, False]
    assert out.loc[0, "mulheres_15_49"] == 30
    assert pd.isna(out.loc[2, "mulheres_15_49"])


def test_agregacao_municipal_cwr_e_razao_de_somas() -> None:
    universo = pd.DataFrame(
        {
            "codigo_setor": ["350000005000001", "350000005000002", "350000005000003"],
            "codigo_ibge": ["3500000"] * 3,
        }
    )
    setores = _derivar_setores(universo, _demografia())
    out = _agregar_municipios(setores, {"3500000": "Teste"}).iloc[0]
    # CWR municipal = soma das crianças / soma das mulheres no universo válido:
    # (4 + 10) / (30 + 60) * 1000, e não média simples das razões setoriais.
    assert out["cwr_0_4_por_1000_m1549"] == pytest.approx(14 / 90 * 1000)
    assert out["mulheres_15_49_validas"] == 90
    assert out["setores_validos_m1549"] == 2
    assert out["setores_validos_cwr"] == 2
