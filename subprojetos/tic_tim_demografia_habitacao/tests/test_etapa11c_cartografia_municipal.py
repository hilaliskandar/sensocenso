import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import box

from tic_tim_demografia.cartografia_municipal_dados import (
    classificar_quantis,
    dissolver_setores_municipais,
    montar_dados_municipais,
    predominancia_familias,
)


def test_classificar_quantis_preserva_ausencia_e_limites():
    serie = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, np.nan])
    classes, bins, rotulos = classificar_quantis(serie, n_classes=5)
    assert len(rotulos) == 5
    assert len(bins) == 6
    assert classes.iloc[-1] is pd.NA or pd.isna(classes.iloc[-1])
    assert classes.iloc[:-1].notna().all()
    assert bins[0] == 1.0
    assert bins[-1] == 10.0


def test_predominancia_familias_preserva_empate():
    base = pd.DataFrame(
        {
            "codigo_ibge": ["1000001"] * 4 + ["1000002"] * 4,
            "FLAG_UNIVERSO_INTEGRADO": [True] * 8,
            "F1": [1, 1, 0, 0, 0, 0, 0, 0],
            "F2": [0, 0, 0, 0, 1, 1, 1, 0],
            "F3": [0, 0, 0, 0, 0, 0, 0, 0],
            "F4": [1, 1, 0, 0, 0, 0, 0, 0],
        }
    )
    out = predominancia_familias(base).set_index("codigo_ibge")
    assert out.loc["1000001", "M14"] == "F1+F4"
    assert out.loc["1000002", "M14"] == "F2"
    assert out.loc["1000001", "pct_f1"] == 50.0
    assert out.loc["1000001", "pct_f4"] == 50.0


def test_dissolver_setores_municipais_gera_territorio_integral_por_codigo():
    setores = gpd.GeoDataFrame(
        {
            "CD_SETOR": ["100000100000001", "100000100000002", "100000200000001"],
            "geometry": [box(0, 0, 1, 1), box(1, 0, 2, 1), box(3, 0, 4, 1)],
        },
        crs="EPSG:31983",
    )
    limites = dissolver_setores_municipais(
        setores, "CD_SETOR", {"1000001", "1000002"}
    ).set_index("codigo_ibge")
    assert len(limites) == 2
    assert limites.loc["1000001", "geometry"].area == 2.0
    assert limites.loc["1000002", "geometry"].area == 1.0


def test_montar_dados_municipais_fecha_30_e_preserva_unidades():
    codigos = [f"{3500000 + i:07d}" for i in range(30)]
    linhas_long = []
    for i, codigo in enumerate(codigos):
        for ano, pop, re in (
            (2010, 1000 + i * 10, 50 + i),
            (2022, 1100 + i * 12, 60 + i),
        ):
            linhas_long.append(
                {
                    "codigo_ibge": codigo,
                    "ano": ano,
                    "municipio_config": f"Município {i:02d}",
                    "pop_total_harmonizada": pop,
                    "razao_envelhecimento": re,
                }
            )
    longitudinal = pd.DataFrame(linhas_long)
    renovacao = pd.DataFrame(
        {
            "codigo_ibge": codigos,
            "cwr_0_4_por_1000_m1549": [200.0 + i for i in range(30)],
        }
    )
    sintese = pd.DataFrame(
        {
            "codigo_ibge": codigos,
            "agua_fora_rede": [0.01 + i / 10000 for i in range(30)],
            "esgotamento_inadequado": [0.02 + i / 10000 for i in range(30)],
        }
    )
    distributivas = pd.DataFrame(
        {
            "codigo_ibge": codigos,
            "pct_preta_parda_urbano": [0.30 + i / 1000 for i in range(30)],
        }
    )
    familias = pd.DataFrame(
        {
            "codigo_ibge": codigos,
            "FLAG_UNIVERSO_INTEGRADO": [True] * 30,
            "F1": [1] * 30,
            "F2": [0] * 30,
            "F3": [0] * 30,
            "F4": [0] * 30,
        }
    )
    out = montar_dados_municipais(
        longitudinal, renovacao, sintese, distributivas, familias
    )
    assert len(out) == 30
    assert out["codigo_ibge"].nunique() == 30
    assert out["M05"].iloc[0] == 30.0
    assert out["M10"].iloc[0] == 1.0
    assert out["M11"].iloc[0] == 2.0
    assert set(out["M14"]) == {"F1"}
