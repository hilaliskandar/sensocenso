import re

import pytest

from tic_tim_demografia.etapa03a import (
    PADRAO_BASICO,
    PADRAO_DOMICILIO1,
    _localizar_numero_moradores,
    _selecionar_unico,
)
from tic_tim_demografia.fontes.sidra_descritor import Categoria, Classificacao


def test_localiza_numero_moradores_pelo_nome():
    classificacoes = [
        Classificacao(
            "99",
            "Número de moradores",
            (
                Categoria("1", "1 morador"),
                Categoria("2", "2 moradores"),
                Categoria("3", "3 moradores"),
                Categoria("4", "4 moradores"),
                Categoria("5", "5 moradores"),
            ),
        )
    ]
    encontrada = _localizar_numero_moradores(classificacoes)
    assert encontrada.codigo == "99"


def test_localiza_numero_moradores_por_estrutura_quando_rotulo_varia():
    classificacoes = [
        Classificacao(
            "42",
            "Quantidade no domicílio",
            (
                Categoria("a", "1 pessoa"),
                Categoria("b", "2 pessoas"),
                Categoria("c", "3 pessoas"),
                Categoria("d", "4 pessoas"),
                Categoria("e", "5 pessoas"),
            ),
        ),
        Classificacao(
            "7",
            "Outra classificação",
            (Categoria("1", "A"), Categoria("2", "B")),
        ),
    ]
    encontrada = _localizar_numero_moradores(classificacoes)
    assert encontrada.codigo == "42"


def test_localizador_recusa_ambiguidade_estrutural():
    base = (
        Categoria("a", "1 pessoa"),
        Categoria("b", "2 pessoas"),
        Categoria("c", "3 pessoas"),
        Categoria("d", "4 pessoas"),
        Categoria("e", "5 pessoas"),
    )
    classificacoes = [
        Classificacao("1", "A", base),
        Classificacao("2", "B", base),
    ]
    with pytest.raises(ValueError, match="ambígua/ausente"):
        _localizar_numero_moradores(classificacoes)


def test_seleciona_arquivos_2022_com_ou_sem_data():
    links = [
        "https://exemplo/Agregados_por_setores_basico_BR_20260520.zip",
        "https://exemplo/Agregados_por_setores_caracteristicas_domicilio1_BR.zip",
        "https://exemplo/Agregados_por_setores_demografia_BR.zip",
    ]
    assert "basico" in _selecionar_unico(links, PADRAO_BASICO, "basico").lower()
    assert "domicilio1" in _selecionar_unico(
        links, PADRAO_DOMICILIO1, "domicilio1"
    ).lower()


def test_seleciona_unico_recusa_duas_edicoes_compativeis():
    links = [
        "https://exemplo/Agregados_por_setores_basico_BR.zip",
        "https://exemplo/Agregados_por_setores_basico_BR_20260520.zip",
    ]
    with pytest.raises(ValueError, match="ambígua/ausente"):
        _selecionar_unico(links, PADRAO_BASICO, "basico")


def test_padroes_nao_aceitam_temas_errados():
    assert not PADRAO_BASICO.match("Agregados_por_setores_demografia_BR.zip")
    assert not PADRAO_DOMICILIO1.match("Agregados_por_setores_caracteristicas_domicilio2_BR.zip")
    assert isinstance(PADRAO_DOMICILIO1, re.Pattern)
