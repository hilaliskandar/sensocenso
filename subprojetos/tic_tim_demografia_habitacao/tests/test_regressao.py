from pathlib import Path

import pandas as pd
import pytest

from tic_tim_demografia.qa.regressao import carregar_oraculo_csv, comparar_com_oraculo


FIXTURE = Path(__file__).parent / "fixtures/oraculo_longitudinal_2000_2010_sentinelas.csv"


def test_oraculo_sentinelas_tem_casos_criticos():
    ref = carregar_oraculo_csv(FIXTURE)
    assert len(ref) == 20
    assert ref["codigo_ibge"].nunique() == 10
    assert set(ref["ano"]) == {2000, 2010}
    assert {"3525904", "3548005"}.issubset(set(ref["codigo_ibge"]))


def test_comparacao_exata_aprova_base_igual():
    ref = carregar_oraculo_csv(FIXTURE)
    resultado = comparar_com_oraculo(ref.copy(), ref)
    assert resultado["status"] == "OK"
    assert resultado["divergencias"] == 0


def test_comparacao_detecta_um_erro_de_uma_pessoa():
    ref = carregar_oraculo_csv(FIXTURE)
    produzido = ref.copy()
    mask = (produzido["codigo_ibge"] == "3525904") & (produzido["ano"] == 2010)
    produzido.loc[mask, "pop_15_59"] += 1
    produzido.loc[mask, "pop_total_harmonizada"] += 1
    with pytest.raises(AssertionError, match="Gate de regressão reprovado"):
        comparar_com_oraculo(produzido, ref)


def test_comparacao_rejeita_chave_ausente():
    ref = carregar_oraculo_csv(FIXTURE)
    produzido = ref.iloc[:-1].copy()
    with pytest.raises(AssertionError, match="Chaves do oráculo ausentes"):
        comparar_com_oraculo(produzido, ref)
