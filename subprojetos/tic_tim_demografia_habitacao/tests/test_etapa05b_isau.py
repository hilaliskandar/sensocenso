from __future__ import annotations

import zipfile

from tic_tim_demografia.etapa05b import (
    VARIAVEIS_AER,
    _mapear_variaveis,
    _selecionar_domicilios,
    inspecionar_zip,
)


def test_seleciona_apenas_tres_arquivos_domiciliares_gerais():
    urls = [
        "https://exemplo/Agregados_por_setores_caracteristicas_domicilio1_BR.zip",
        "https://exemplo/Agregados_por_setores_caracteristicas_domicilio2_BR_20250417.zip",
        "https://exemplo/Agregados_por_setores_caracteristicas_domicilio3_BR_20250417.zip",
        "https://exemplo/Agregados_por_setores_domicilios_indigenas_BR.zip",
    ]
    selecionados = _selecionar_domicilios(urls)
    assert len(selecionados) == 3
    assert all("caracteristicas_domicilio" in x for x in selecionados)


def test_inspecao_zip_le_so_cabecalho_e_mapeia_variaveis(tmp_path):
    path = tmp_path / "domicilio1.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "Agregados_por_setores_caracteristicas_domicilio1_BR.csv",
            "CD_SETOR;V00001;V00464;OUTRA\n350000000000001;10;2;9\n",
        )
    info = inspecionar_zip(path)
    assert len(info["csvs"]) == 1
    assert info["csvs"][0]["separador"] == ";"
    assert info["csvs"][0]["colunas"] == ["CD_SETOR", "V00001", "V00464", "OUTRA"]

    mapa = _mapear_variaveis([info], VARIAVEIS_AER)
    assert len(mapa["V00001"]) == 1
    assert len(mapa["V00464"]) == 1
    assert mapa["V00312"] == []
