import pytest

from tic_tim_demografia.harmonizacao.idade import (
    banda_harmonizada,
    interpretar_faixa_etaria,
    mapear_rotulos_para_bandas,
    selecionar_particao_quinquenal,
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


def test_particao_quinquenal_ignora_idades_simples_e_agregados_sobrepostos():
    rotulos = ["Total", "Menos de 1 ano", "1 a 4 anos", "80 anos ou mais"]
    for inicio in range(0, 100, 5):
        rotulos.append(f"{inicio} a {inicio + 4} anos")
    rotulos.append("100 anos ou mais")
    rotulos.extend(["1 ano", "2 anos", "15 anos", "20 anos"])

    mapa = selecionar_particao_quinquenal(rotulos)
    assert len(mapa) == 21
    assert "0 a 4 anos" in mapa
    assert "1 ano" not in mapa
    assert "1 a 4 anos" not in mapa
    assert "80 anos ou mais" not in mapa
    assert mapa["100 anos ou mais"] == "60_mais"


def test_particao_quinquenal_falha_se_houver_lacuna():
    rotulos = [f"{inicio} a {inicio + 4} anos" for inicio in range(0, 100, 5)]
    rotulos.remove("35 a 39 anos")
    rotulos.append("100 anos ou mais")
    with pytest.raises(ValueError, match="partição etária quinquenal completa"):
        selecionar_particao_quinquenal(rotulos)
