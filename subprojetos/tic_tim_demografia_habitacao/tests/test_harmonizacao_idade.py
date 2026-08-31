from tic_tim_demografia.harmonizacao.idade import (
    banda_harmonizada,
    interpretar_faixa_etaria,
    mapear_rotulos_para_bandas,
)


def test_interpreta_intervalos_e_abertos():
    f = interpretar_faixa_etaria("10 a 14 anos")
    assert f is not None and (f.minimo, f.maximo) == (10, 14)

    g = interpretar_faixa_etaria("80 anos ou mais")
    assert g is not None and (g.minimo, g.maximo) == (80, None)


def test_nao_aloca_faixa_que_cruza_limite_harmonizado():
    f = interpretar_faixa_etaria("10 a 19 anos")
    assert f is not None
    assert banda_harmonizada(f) is None


def test_mapeia_bandas_sem_interpolar():
    mapa = mapear_rotulos_para_bandas(
        ["0 a 4 anos", "5 a 9 anos", "10 a 14 anos", "15 a 19 anos", "60 a 64 anos", "Total"]
    )
    assert mapa["0 a 4 anos"] == "0_14"
    assert mapa["15 a 19 anos"] == "15_59"
    assert mapa["60 a 64 anos"] == "60_mais"
    assert "Total" not in mapa
