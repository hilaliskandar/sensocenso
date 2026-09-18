from tic_tim_demografia.fontes.sidra import (
    construir_caminho_sidra,
    dividir_lotes,
    traduzir_caminho_sidra_para_agregados,
)


def test_construir_caminho_sidra_municipal() -> None:
    caminho = construir_caminho_sidra(
        tabela=1518,
        nivel_territorial=6,
        localidades=[3501608, 3503802],
        variaveis="allxp",
        periodos=[2000],
        classificacoes={2: "all", 1: [0]},
    )
    assert caminho.startswith("t/1518/n6/3501608,3503802/v/allxp/p/2000/")
    assert "/c1/0/c2/all/" in f"/{caminho}/"
    assert caminho.endswith("h/y/f/a/d/m")


def test_dividir_lotes() -> None:
    lotes = dividir_lotes([str(i) for i in range(23)], 10)
    assert [len(x) for x in lotes] == [10, 10, 3]


def test_traduzir_caminho_sidra_para_agregados() -> None:
    caminho = construir_caminho_sidra(
        tabela=1518,
        nivel_territorial=6,
        localidades=[3509007, 3509502],
        variaveis="allxp",
        periodos=[2000],
        classificacoes={1: 0, 2: 0, 58: [1140, 1141]},
    )
    url = traduzir_caminho_sidra_para_agregados(caminho)
    assert url.startswith(
        "https://servicodados.ibge.gov.br/api/v3/agregados/1518/periodos/2000/variaveis/allxp?"
    )
    assert "localidades=N6[3509007,3509502]" in url
    assert "classificacao=1[0]|2[0]|58[1140,1141]" in url
    assert url.endswith("&view=flat")


def test_traduzir_last_para_periodo_negativo() -> None:
    caminho = construir_caminho_sidra(
        tabela=6579,
        nivel_territorial=3,
        localidades="all",
        variaveis="allxp",
        periodos="last",
    )
    url = traduzir_caminho_sidra_para_agregados(caminho)
    assert "/periodos/-1/" in url
