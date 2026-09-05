from tic_tim_demografia.fontes.sidra import construir_caminho_sidra, dividir_lotes


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
