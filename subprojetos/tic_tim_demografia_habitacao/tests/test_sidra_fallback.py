from __future__ import annotations

import json
from pathlib import Path

from tic_tim_demografia.fontes.sidra import (
    SidraClient,
    baixar_descritor_tabela,
    normalizar_descritor_agregados,
)
from tic_tim_demografia.fontes.sidra_descritor import extrair_classificacoes


def _payload_agregados() -> list[dict]:
    return [
        {
            "id": "93",
            "variavel": "População residente",
            "unidade": "Pessoas",
            "resultados": [
                {
                    "classificacoes": [
                        {
                            "id": "1",
                            "nome": "Situação do domicílio",
                            "categoria": {"0": "Total", "1": "Urbana", "2": "Rural"},
                        },
                        {
                            "id": "2",
                            "nome": "Sexo",
                            "categoria": {"0": "Total", "4": "Homens", "5": "Mulheres"},
                        },
                        {
                            "id": "58",
                            "nome": "Grupos de idade",
                            "categoria": {
                                "0": "Total",
                                "1140": "0 a 4 anos",
                                "1141": "5 a 9 anos",
                                "1142": "10 a 14 anos",
                                "1143": "15 a 19 anos",
                                "1163": "60 a 64 anos",
                            },
                        },
                    ],
                    "series": [],
                }
            ],
        },
        {
            "id": "93",
            "variavel": "População residente",
            "unidade": "Pessoas",
            "resultados": [
                {
                    "classificacoes": [
                        {
                            "id": "1",
                            "nome": "Situação do domicílio",
                            "categoria": {"0": "Total", "1": "Urbana"},
                        }
                    ],
                    "series": [],
                }
            ],
        },
    ]


def test_agregados_normaliza_para_contrato_do_descritor() -> None:
    descritor = normalizar_descritor_agregados(_payload_agregados())
    classificacoes = extrair_classificacoes(descritor)

    assert descritor["origem"] == "ibge_api_agregados_v3"
    assert [(c.codigo, c.nome) for c in classificacoes] == [
        ("1", "Situação do domicílio"),
        ("2", "Sexo"),
        ("58", "Grupos de idade"),
    ]
    situacao = classificacoes[0]
    assert [(c.codigo, c.nome) for c in situacao.categorias] == [
        ("0", "Total"),
        ("1", "Urbana"),
        ("2", "Rural"),
    ]
    idade = classificacoes[2]
    assert idade.nome == "Grupos de idade"
    assert any(c.nome == "0 a 4 anos" for c in idade.categorias)
    assert any(c.nome == "60 a 64 anos" for c in idade.categorias)


def test_cliente_agregados_constroi_url_e_normaliza(monkeypatch) -> None:
    chamadas: list[str] = []

    def fake_get_json(self, url: str):
        chamadas.append(url)
        return _payload_agregados()

    monkeypatch.setattr(SidraClient, "_get_json", fake_get_json)
    descritor = SidraClient(tentativas=1).descritor_agregados(1518, 2000)

    assert chamadas == [
        "https://servicodados.ibge.gov.br/api/v3/agregados/1518/"
        "periodos/2000/variaveis?localidades=BR"
    ]
    nomes = {c.nome for c in extrair_classificacoes(descritor)}
    assert {"Situação do domicílio", "Sexo", "Grupos de idade"}.issubset(nomes)


def test_baixar_descritor_usa_fallback_oficial(tmp_path: Path) -> None:
    class ClienteFake:
        def descritor(self, tabela: int):
            raise RuntimeError("ConnectTimeout apisidra")

        def descritor_agregados(self, tabela: int, periodo: str | int):
            assert tabela == 1518
            assert str(periodo) == "2000"
            return normalizar_descritor_agregados(_payload_agregados())

        def salvar_json(self, dados, destino, *, manifesto=None, origem=None, sobrescrever=False):
            assert origem == (
                "https://servicodados.ibge.gov.br/api/v3/agregados/1518/"
                "periodos/2000/variaveis?localidades=BR"
            )
            destino.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")

    destino = tmp_path / "descritor_tabela_1518.json"
    resultado = baixar_descritor_tabela(
        1518,
        destino,
        periodo_fallback=2000,
        cliente=ClienteFake(),
    )

    assert resultado == destino
    assert destino.exists()
    classificacoes = extrair_classificacoes(
        json.loads(destino.read_text(encoding="utf-8"))
    )
    assert {c.nome for c in classificacoes} == {
        "Situação do domicílio",
        "Sexo",
        "Grupos de idade",
    }
