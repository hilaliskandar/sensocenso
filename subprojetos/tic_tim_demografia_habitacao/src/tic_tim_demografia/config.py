from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Municipio:
    codigo_ibge: str
    nome: str
    coroa: str


def _ler_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Configuração YAML inválida: {path}")
    return data


def carregar_municipios(path: Path) -> list[Municipio]:
    data = _ler_yaml(path)
    itens = data.get("municipios", [])
    municipios = [
        Municipio(
            codigo_ibge=str(item["codigo_ibge"]),
            nome=str(item["nome"]),
            coroa=str(item["coroa"]),
        )
        for item in itens
    ]
    validar_municipios(municipios, data.get("validacao", {}))
    return municipios


def validar_municipios(municipios: list[Municipio], regras: dict[str, Any]) -> None:
    esperados = int(regras.get("quantidade_esperada", 30))
    if len(municipios) != esperados:
        raise ValueError(f"Universo municipal inválido: {len(municipios)} != {esperados}")

    codigos = [m.codigo_ibge for m in municipios]
    nomes = [m.nome for m in municipios]
    if len(set(codigos)) != len(codigos):
        raise ValueError("Há códigos IBGE municipais duplicados.")
    if len(set(nomes)) != len(nomes):
        raise ValueError("Há nomes municipais duplicados.")

    invalidos = [c for c in codigos if len(c) != 7 or not c.isdigit()]
    if invalidos:
        raise ValueError(f"Códigos IBGE inválidos: {invalidos}")

    excluidos = {str(x) for x in regras.get("excluir_codigos", [])}
    presentes_excluidos = sorted(excluidos.intersection(codigos))
    if presentes_excluidos:
        raise ValueError(f"Código explicitamente excluído presente: {presentes_excluidos}")

    internas = sum(m.coroa == "interna" for m in municipios)
    externas = sum(m.coroa == "externa" for m in municipios)
    exp_internas = int(regras.get("quantidade_coroa_interna", 10))
    exp_externas = int(regras.get("quantidade_coroa_externa", 20))
    if (internas, externas) != (exp_internas, exp_externas):
        raise ValueError(
            "Distribuição de coroas inválida: "
            f"interna={internas}/{exp_internas}, externa={externas}/{exp_externas}"
        )

    corrigidos = {str(k): str(v) for k, v in regras.get("codigos_corrigidos", {}).items()}
    por_nome = {m.nome: m.codigo_ibge for m in municipios}
    divergentes = {
        nome: {"esperado": codigo, "observado": por_nome.get(nome)}
        for nome, codigo in corrigidos.items()
        if por_nome.get(nome) != codigo
    }
    if divergentes:
        raise ValueError(f"Códigos auditados divergentes: {divergentes}")


def carregar_parametros(path: Path) -> dict[str, Any]:
    return _ler_yaml(path)


def carregar_fontes(path: Path) -> dict[str, Any]:
    return _ler_yaml(path)
