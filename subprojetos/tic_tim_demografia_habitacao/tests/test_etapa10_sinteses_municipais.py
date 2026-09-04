import pandas as pd
import pytest

from tic_tim_demografia.etapa10_corrente import (
    ATRIBUTOS_ENTORNO,
    UNIVERSOS_ENTORNO,
    _agregar_entorno,
    _correlacao_spearman,
    _percentil_relativo,
    _proporcao_composicional,
)


def test_proporcao_composicional_domicilios_5mais():
    cols = [f"V000{i:02d}" for i in range(17, 27)]
    somas = pd.DataFrame([[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]], columns=cols, index=["3500000"])
    obtido = _proporcao_composicional(
        somas,
        ["V00021", "V00022", "V00023", "V00024", "V00025", "V00026"],
        cols,
    )
    assert obtido.iloc[0] == pytest.approx((5 + 6 + 7 + 8 + 9 + 10) / sum(range(1, 11)))


def test_percentil_relativo_usa_postos_medios_em_empates():
    serie = pd.Series([10.0, 20.0, 20.0, 40.0], index=list("abcd"))
    obtido = _percentil_relativo(serie)
    assert obtido.to_dict() == pytest.approx({"a": 0.25, "b": 0.625, "c": 0.625, "d": 1.0})


def test_spearman_exclui_ausencias_apenas_no_par():
    x = pd.Series([1.0, 2.0, 3.0, 4.0])
    y = pd.Series([1.0, 2.0, pd.NA, 4.0], dtype="Float64")
    obtido = _correlacao_spearman(x, y)
    assert obtido["n"] == 3
    assert obtido["rho"] == pytest.approx(1.0)


def test_entorno_trata_obstaculo_com_sinal_inverso_dos_demais_atributos():
    linha = {"codigo_ibge": "3500000"}
    for universo in UNIVERSOS_ENTORNO:
        for atributo in ATRIBUTOS_ENTORNO:
            prefixo = f"{universo}_{atributo}"
            if atributo == "obstaculo_calcada":
                linha[f"{prefixo}_sim"] = 3.0
                linha[f"{prefixo}_nao"] = 7.0
            else:
                linha[f"{prefixo}_sim"] = 7.0
                linha[f"{prefixo}_nao"] = 3.0
            linha[f"{prefixo}_den_valido"] = 10.0
    base = pd.DataFrame([linha])
    obtido = _agregar_entorno(base)
    assert obtido.loc["3500000", "entorno_obstaculo_calcada"] == pytest.approx(0.3)
    for atributo in ATRIBUTOS_ENTORNO:
        assert obtido.loc["3500000", f"entorno_{atributo}"] == pytest.approx(0.3)
