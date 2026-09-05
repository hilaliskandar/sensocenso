import numpy as np
import pandas as pd
import pytest

from tic_tim_demografia.etapa11b_graficos import (
    _proporcao_regional_de_somas,
    dados_g02,
    dados_g04,
    dados_g05,
    dados_g06,
    dados_g11,
    dados_g13,
    plot_g02,
)


def _longitudinal_30():
    linhas = []
    for i in range(30):
        codigo = str(3500000 + i)
        for ano, total, jovens, idosos in (
            (2000, 100, 30, 10),
            (2010, 120, 25, 18),
            (2022, 150, 24, 30),
        ):
            linhas.append(
                {
                    "codigo_ibge": codigo,
                    "ano": ano,
                    "pop_0_14": jovens,
                    "pop_15_59": total - jovens - idosos,
                    "pop_60_mais": idosos,
                    "pop_total_harmonizada": total,
                    "municipio_config": f"M{i:02d}",
                    "razao_envelhecimento": 100 * idosos / jovens,
                }
            )
    return pd.DataFrame(linhas)


def _domicilios_30():
    linhas = []
    for i in range(30):
        codigo = str(3500000 + i)
        for ano, dpo, moradores, unip in (
            (2000, 40, 140, 4),
            (2010, 48, 144, 6),
            (2022, 60, 150, 12),
        ):
            linhas.append(
                {
                    "codigo_ibge": codigo,
                    "municipio": f"M{i:02d} (SP)",
                    "ano": ano,
                    "dpo": dpo,
                    "moradores_dpo": moradores,
                    "tam_medio": moradores / dpo,
                    "dpp_num_moradores": dpo,
                    "unipessoais": unip,
                    "pct_unipessoais": unip / dpo,
                }
            )
    return pd.DataFrame(linhas)


def test_g02_sintese_regional_fecha_100_e_renderiza(tmp_path):
    out = dados_g02(_longitudinal_30())
    assert out["ano"].tolist() == [2000, 2010, 2022]
    assert np.allclose(out[["pct_0_14", "pct_15_59", "pct_60_mais"]].sum(axis=1), 100.0)
    assert out.loc[out["ano"].eq(2022), "pct_60_mais"].iloc[0] > out.loc[out["ano"].eq(2000), "pct_60_mais"].iloc[0]
    arquivos = plot_g02(out, tmp_path)
    assert {p.suffix for p in arquivos} == {".png", ".svg"}
    assert all(p.exists() and p.stat().st_size > 0 for p in arquivos)


def test_g04_preserva_30_municipios_e_diferenca_de_crescimento():
    out = dados_g04(_longitudinal_30(), _domicilios_30())
    assert len(out) == 30
    assert out["crescimento_pop_2010_2022_pct"].iloc[0] == pytest.approx(25.0)
    assert out["crescimento_dpo_2010_2022_pct"].iloc[0] == pytest.approx(25.0)
    assert out["diferenca_dpo_menos_pop_pp"].iloc[0] == pytest.approx(0.0)


def test_g05_e_g06_preservam_transformacoes_domiciliares():
    dom = _domicilios_30()
    g05 = dados_g05(dom)
    assert len(g05) == 30
    assert g05["variacao_2000_2022"].lt(0).all()

    regional, municipal = dados_g06(dom)
    assert len(municipal) == 30
    assert municipal["variacao_2000_2022_pp"].gt(0).all()
    assert regional.loc[regional["ano"].eq(2022), "unipessoais"].iloc[0] == 360
    assert regional.loc[regional["ano"].eq(2022), "pct_unipessoais"].iloc[0] == pytest.approx(20.0)


def test_proporcao_regional_reconstroi_numerador_e_denominador():
    somas = pd.DataFrame({"a": [10, 20], "b": [90, 80]})
    num, den, prop = _proporcao_regional_de_somas(somas, ["a"], ["a", "b"])
    assert num == 30
    assert den == 200
    assert prop == pytest.approx(0.15)


def test_g11_e_g13_calculam_spearman_em_30_municipios():
    codigos = [str(3500000 + i) for i in range(30)]
    sintese = pd.DataFrame(
        {
            "codigo_ibge": codigos,
            "municipio": [f"M{i:02d}" for i in range(30)],
            "gravidade_fisico_urbana": [i / 29 for i in range(30)],
            "crescimento_dpo_2010_2022": [(29 - i) / 100 for i in range(30)],
        }
    )
    distributivas = pd.DataFrame(
        {
            "codigo_ibge": codigos,
            "pct_preta_parda_urbano": [0.2 + i / 100 for i in range(30)],
        }
    )
    g11, c11 = dados_g11(sintese, distributivas)
    g13, c13 = dados_g13(sintese)
    assert len(g11) == len(g13) == 30
    assert c11["n"] == c13["n"] == 30
    assert c11["rho"] == pytest.approx(1.0)
    assert c13["rho"] == pytest.approx(-1.0)
