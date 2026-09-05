import numpy as np
import pandas as pd
import pytest

from tic_tim_demografia.cartografia_setorial_dados import (
    categorizar_m08,
    categorizar_m09,
    classificar_zero_mais_quantis,
    preparar_m12,
    selecionar_insets_m04,
    selecionar_insets_m06,
    selecionar_insets_m08,
)


def test_classificar_zero_mais_quantis_preserva_zero_positivos_e_ausencia():
    serie = pd.Series([0, 0, 1, 2, 3, 4, 5, 6, 7, 8, np.nan])
    classes, limites, rotulos = classificar_zero_mais_quantis(serie)
    assert rotulos[0] == "0"
    assert classes.iloc[0] == "0"
    assert classes.iloc[2:10].notna().all()
    assert pd.isna(classes.iloc[-1])
    assert limites[0] == 0.0
    assert limites[-1] == 8.0


def test_categorizar_m08_preserva_triestado_e_numero_de_dimensoes():
    base = pd.DataFrame(
        {
            "CONVERGENCIA_3_OU_4": [0, 1, 1, pd.NA],
            "N_FAMILIAS_SINAL": [2, 3, 4, 2],
        }
    )
    out = categorizar_m08(base)
    assert out.tolist() == [
        "0–2 dimensões",
        "3 dimensões",
        "4 dimensões",
        "Classificação indeterminada",
    ]


def test_categorizar_m08_rejeita_convergencia_incompativel():
    base = pd.DataFrame(
        {"CONVERGENCIA_3_OU_4": [1], "N_FAMILIAS_SINAL": [2]}
    )
    with pytest.raises(AssertionError):
        categorizar_m08(base)


def test_categorizar_m09_distingue_persistencia_composicao_e_indeterminacao():
    base = pd.DataFrame(
        {
            "CONVERGENCIA_3_OU_4": [0, pd.NA, 1, 1, 1, 1],
            "CONVERGENCIA_3_OU_4_P80": [0, 0, pd.NA, 0, 1, 1],
            "PERSISTENTE_P75_P80": [0, pd.NA, pd.NA, 0, 1, 1],
            "MESMO_VETOR_P75_P80": [1, 1, 1, 1, 0, 1],
        }
    )
    assert categorizar_m09(base).tolist() == [
        "Fora do critério P75",
        "P75 indeterminado",
        "P75, P80 indeterminado",
        "P75, não persistente no P80",
        "Persistente, composição alterada",
        "Persistente, mesmo vetor",
    ]


def test_seletores_de_insets_sao_deterministicos():
    linhas = []
    for codigo, nome, vals_cwr, vals_priv, conv in (
        ("1", "A", [0, 10, 20, 30], [0.1, 0.1, 0.1, 0.1], [0, 0, 0, 0]),
        ("2", "B", [0, 20, 40, 60], [0.3, 0.3, 0.3, 0.3], [1, 1, 0, 0]),
        ("3", "C", [0, 30, 60, 90], [0.2, 0.2, 0.2, 0.2], [1, 1, 1, 0]),
    ):
        for i in range(4):
            linhas.append(
                {
                    "codigo_ibge": codigo,
                    "municipio": nome,
                    "codigo_setor": f"{codigo}-{i}",
                    "cwr_0_4_por_1000_m1549": vals_cwr[i],
                    "PRIV_C3": vals_priv[i],
                    "CONVERGENCIA_3_OU_4": conv[i],
                }
            )
    base = pd.DataFrame(linhas)
    assert [x.municipio for x in selecionar_insets_m04(base, 2)] == ["C", "B"]
    assert [x.municipio for x in selecionar_insets_m06(base, 2)] == ["B", "C"]
    assert [x.municipio for x in selecionar_insets_m08(base, 2)] == ["C", "B"]


def test_preparar_m12_exige_universo_e_componentes():
    cols = {
        "codigo_setor": ["1", "2"],
        "codigo_ibge": ["10", "10"],
        "moradores_bueiro_boca_de_lobo_pct_nao": [0.0, 1.0],
        "moradores_calcada_pct_nao": [0.0, 2.0],
        "moradores_pavimentacao_pct_nao": [0.0, 3.0],
        "moradores_arborizacao_pct_nao": [0.0, 4.0],
        "moradores_iluminacao_publica_pct_nao": [0.0, 5.0],
    }
    out = preparar_m12(pd.DataFrame(cols), esperado=2)
    assert len(out) == 2
    duplicada = pd.DataFrame(cols)
    duplicada.loc[1, "codigo_setor"] = "1"
    with pytest.raises(AssertionError):
        preparar_m12(duplicada, esperado=2)
