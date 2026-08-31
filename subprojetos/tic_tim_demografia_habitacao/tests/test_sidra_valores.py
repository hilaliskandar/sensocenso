import pandas as pd
import pytest

from tic_tim_demografia.harmonizacao.sidra_valores import (
    agregar_bandas_etarias,
    converter_valores_sidra,
    normalizar_resposta_sidra,
    resolver_colunas_harmonizacao,
)


def _resposta_exemplo(valor_extra_variavel: bool = False):
    cab = {
        "NC": "Nível Territorial (Código)",
        "NN": "Nível Territorial",
        "MC": "Unidade de Medida (Código)",
        "MN": "Unidade de Medida",
        "V": "Valor",
        "D1C": "Município (Código)",
        "D1N": "Município",
        "D2C": "Variável (Código)",
        "D2N": "Variável",
        "D3C": "Ano (Código)",
        "D3N": "Ano",
        "D4C": "Grupos de idade (Código)",
        "D4N": "Grupos de idade",
    }
    linhas = [cab]
    for codigo_mun, nome in (("3503802", "Artur Nogueira"), ("3525904", "Jundiaí")):
        for cat, rotulo, valor in (("1", "0 a 14 anos", "100"), ("2", "15 a 59 anos", "300"), ("3", "60 anos ou mais", "50")):
            linhas.append({
                "NC": "6", "NN": "Município", "MC": "45", "MN": "Pessoas", "V": valor,
                "D1C": codigo_mun, "D1N": nome, "D2C": "93", "D2N": "População residente",
                "D3C": "2000", "D3N": "2000", "D4C": cat, "D4N": rotulo,
            })
    if valor_extra_variavel:
        extra = dict(linhas[-1])
        extra["D2C"] = "999"
        extra["D2N"] = "Outra variável"
        linhas.append(extra)
    return linhas


def test_normaliza_e_agrega_bandas_com_ano():
    df = normalizar_resposta_sidra(_resposta_exemplo())
    cols = resolver_colunas_harmonizacao(df, "Grupos de idade")
    out = agregar_bandas_etarias(
        df,
        colunas=cols,
        codigo_para_banda={"1": "0_14", "2": "15_59", "3": "60_mais"},
        ano_esperado=2000,
    )
    assert len(out) == 2
    assert set(out["pop_total_harmonizada"]) == {450}
    assert set(out["ano"]) == {2000}


def test_multiplas_variaveis_falham_em_vez_de_somar():
    df = normalizar_resposta_sidra(_resposta_exemplo(valor_extra_variavel=True))
    cols = resolver_colunas_harmonizacao(df, "Grupos de idade")
    with pytest.raises(ValueError, match="múltiplas variáveis"):
        agregar_bandas_etarias(
            df,
            colunas=cols,
            codigo_para_banda={"1": "0_14", "2": "15_59", "3": "60_mais"},
            ano_esperado=2000,
        )


def test_hifen_convencional_vira_zero():
    convertido = converter_valores_sidra(pd.Series(["-", "0", "12"]))
    assert convertido.tolist() == [0, 0, 12]


def test_valor_especial_nao_vira_zero():
    dados = _resposta_exemplo()
    dados[1]["V"] = ".."
    df = normalizar_resposta_sidra(dados)
    cols = resolver_colunas_harmonizacao(df, "Grupos de idade")
    with pytest.raises(ValueError, match="não numéricos"):
        agregar_bandas_etarias(
            df,
            colunas=cols,
            codigo_para_banda={"1": "0_14", "2": "15_59", "3": "60_mais"},
            ano_esperado=2000,
        )
