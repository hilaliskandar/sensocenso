import pandas as pd
import pytest

from tic_tim_demografia.etapa02c import (
    _comparar_oraculo_territorial,
    _validar_matriz_longitudinal,
)


def test_oraculo_sem_sobreposicao_e_nao_aplicavel_ao_novo_territorio():
    produzido = pd.DataFrame({"codigo_ibge": ["3500105", "3500204"]})
    oraculo = pd.DataFrame({"codigo_ibge": ["3550308", "3509502"]})

    resultado = _comparar_oraculo_territorial(produzido, oraculo)

    assert resultado["status"] == "NOT_APPLICABLE_TERRITORY"
    assert resultado["sobreposicao_municipal"] == 0
    assert resultado["divergencias"] is None


def test_oraculo_com_sobreposicao_parcial_e_bloqueante():
    produzido = pd.DataFrame({"codigo_ibge": ["3500105", "3500204"]})
    oraculo = pd.DataFrame({"codigo_ibge": ["3500204", "3550308"]})

    with pytest.raises(AssertionError, match="parcialmente sobreposto"):
        _comparar_oraculo_territorial(produzido, oraculo)


def test_matriz_longitudinal_fecha_para_quantidade_configurada_de_municipios():
    codigos = ["3500105", "3500204", "3500303", "3500402"]
    longitudinal = pd.DataFrame(
        [
            {"codigo_ibge": codigo, "ano": ano}
            for codigo in codigos
            for ano in (2000, 2010, 2022)
        ]
    )

    _validar_matriz_longitudinal(longitudinal, codigos)


def test_matriz_longitudinal_rejeita_ano_ausente_sem_assumir_trinta_municipios():
    codigos = ["3500105", "3500204"]
    longitudinal = pd.DataFrame(
        [
            {"codigo_ibge": "3500105", "ano": 2000},
            {"codigo_ibge": "3500105", "ano": 2010},
            {"codigo_ibge": "3500105", "ano": 2022},
            {"codigo_ibge": "3500204", "ano": 2000},
            {"codigo_ibge": "3500204", "ano": 2010},
        ]
    )

    with pytest.raises(AssertionError, match="Matriz 2×3 não fechou"):
        _validar_matriz_longitudinal(longitudinal, codigos)
