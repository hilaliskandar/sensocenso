from __future__ import annotations

import pandas as pd
import pytest

from tic_tim_demografia.etapa05c import (
    calcular_a,
    calcular_d,
    calcular_e,
    calcular_r,
    calcular_sem_bueiro,
)


def test_componentes_aer_reproduzem_formulas_do_caderno() -> None:
    df = pd.DataFrame(
        {
            "V00001": [100, 100, 100],
            "V00464": [10, "x", 20],
            "V00200": [20, 10, "x"],
            "V00201": [30, 20, "x"],
            "V00312": [1, 1, "x"],
            "V00313": [2, 2, 2],
            "V00314": [3, 3, 3],
            "V00315": [4, 4, 4],
            "V00316": [5, 5, 5],
            "V00399": [1, 1, 1],
            "V00400": [1, 1, 1],
            "V00401": [1, 1, 1],
            "V00402": [1, 1, "x"],
        }
    ).astype("string")

    a = calcular_a(df)
    e = calcular_e(df)
    r = calcular_r(df)

    assert a.loc[0, "A"] == pytest.approx(0.80)
    assert a.loc[1, "A"] == pytest.approx(0.85)
    assert pd.isna(a.loc[2, "A"])
    assert e.loc[0, "E"] == pytest.approx(0.85)
    assert pd.isna(e.loc[2, "E"])
    assert r.loc[0, "R"] == pytest.approx(0.96)
    assert pd.isna(r.loc[2, "R"])


def test_drenagem_exclui_nao_declarado_e_aplica_d2_50_50() -> None:
    df = pd.DataFrame(
        {
            "SIM": [80.0],
            "NAO": [20.0],
            "ND": [900.0],
        }
    ).astype("string")
    audit = calcular_sem_bueiro(
        df, sim="SIM", nao="NAO", nao_declarado="ND", prefixo="teste"
    )
    assert audit.loc[0, "teste_sem_bueiro"] == pytest.approx(0.20)
    assert audit.loc[0, "teste_bueiro_denominador_valido"] == pytest.approx(100.0)

    d = calcular_d(
        pd.Series([0.20]),
        pd.Series([0.40]),
        pd.Series([0.50]),
    )
    # exposicao = media(0.20,0.40)=0.30; privacao D2=0.5*0.30+0.5*0.50=0.40
    assert d.loc[0, "D"] == pytest.approx(0.60)
    assert d.loc[0, "D1"] == pytest.approx(0.60)
    assert d.loc[0, "D3"] == pytest.approx(1.0 - (0.20 + 0.40 + 0.50) / 3.0)


def test_d2_exige_tres_universos() -> None:
    d = calcular_d(
        pd.Series([0.20]),
        pd.Series([0.40]),
        pd.Series([float("nan")]),
    )
    assert pd.isna(d.loc[0, "D"])
    assert pd.isna(d.loc[0, "D3"])
    assert d.loc[0, "D1"] == pytest.approx(0.60)
