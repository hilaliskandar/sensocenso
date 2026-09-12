from pathlib import Path

from tic_tim_demografia.config import carregar_municipios


ROOT = Path(__file__).resolve().parents[1]


def test_universo_municipal_canonico() -> None:
    municipios = carregar_municipios(ROOT / "config/municipios.yml")
    assert len(municipios) == 30
    assert len({m.codigo_ibge for m in municipios}) == 30
    assert sum(m.coroa == "interna" for m in municipios) == 10
    assert sum(m.coroa == "externa" for m in municipios) == 20
    assert all(m.grupo_territorial == m.coroa for m in municipios)
    assert "3550308" not in {m.codigo_ibge for m in municipios}


def test_cinco_codigos_corrigidos() -> None:
    municipios = carregar_municipios(ROOT / "config/municipios.yml")
    por_nome = {m.nome: m.codigo_ibge for m in municipios}
    assert por_nome["Artur Nogueira"] == "3503802"
    assert por_nome["Itatiba"] == "3523404"
    assert por_nome["Itupeva"] == "3524006"
    assert por_nome["Jaguariúna"] == "3524709"
    assert por_nome["Jarinu"] == "3525201"


def test_configuracao_aceita_grupos_territoriais_genericos(tmp_path: Path) -> None:
    path = tmp_path / "municipios.yml"
    path.write_text(
        """municipios:
  - codigo_ibge: '3500001'
    nome: A
    grupo_territorial: subregiao_1
  - codigo_ibge: '3500002'
    nome: B
    grupo_territorial: subregiao_1
  - codigo_ibge: '3500003'
    nome: C
    grupo_territorial: subregiao_2
  - codigo_ibge: '3500004'
    nome: D
    grupo_territorial: subregiao_2
validacao:
  quantidade_esperada: 4
  grupos_esperados:
    subregiao_1: 2
    subregiao_2: 2
""",
        encoding="utf-8",
    )
    municipios = carregar_municipios(path)
    assert [m.grupo_territorial for m in municipios] == [
        "subregiao_1",
        "subregiao_1",
        "subregiao_2",
        "subregiao_2",
    ]
