from __future__ import annotations

import json
from pathlib import Path

from tic_tim_demografia.fontes.sidra import (
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
    ]
    situacao = classificacoes[0]
    assert [(c.codigo, c.nome) for c in situacao.categorias] == [
        ("0", "Total"),
        ("1", "Urbana"),
        ("2", "Rural"),
    ]


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
    assert len(extrair_classificacoes(json.loads(destino.read_text(encoding="utf-8")))) == 2
