from pathlib import Path

from tic_tim_demografia.config import carregar_municipios


ROOT = Path(__file__).resolve().parents[1]


def test_universo_municipal_canonico() -> None:
    municipios = carregar_municipios(ROOT / "config/municipios.yml")
    assert len(municipios) == 30
    assert len({m.codigo_ibge for m in municipios}) == 30
    assert sum(m.coroa == "interna" for m in municipios) == 10
    assert sum(m.coroa == "externa" for m in municipios) == 20
    assert "3550308" not in {m.codigo_ibge for m in municipios}


def test_cinco_codigos_corrigidos() -> None:
    municipios = carregar_municipios(ROOT / "config/municipios.yml")
    por_nome = {m.nome: m.codigo_ibge for m in municipios}
    assert por_nome["Artur Nogueira"] == "3503802"
    assert por_nome["Itatiba"] == "3523404"
    assert por_nome["Itupeva"] == "3524006"
    assert por_nome["Jaguariúna"] == "3524709"
    assert por_nome["Jarinu"] == "3525201"
