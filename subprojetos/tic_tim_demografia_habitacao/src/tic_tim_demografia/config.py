from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Municipio:
    codigo_ibge: str
    nome: str
    grupo_territorial: str

    @property
    def coroa(self) -> str:
        """Alias legado para compatibilidade com o pipeline TIC-TIM existente."""
        return self.grupo_territorial


def _ler_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Configuração YAML inválida: {path}")
    return data


def carregar_municipios(path: Path) -> list[Municipio]:
    data = _ler_yaml(path)
    itens = data.get("municipios", [])
    municipios = []
    for item in itens:
        grupo = item.get("grupo_territorial", item.get("coroa"))
        if grupo is None or not str(grupo).strip():
            raise ValueError(
                f"Município sem grupo territorial/coroa: {item.get('nome', '<sem nome>')}"
            )
        municipios.append(
            Municipio(
                codigo_ibge=str(item["codigo_ibge"]),
                nome=str(item["nome"]),
                grupo_territorial=str(grupo),
            )
        )
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

    contagem_grupos = Counter(m.grupo_territorial for m in municipios)
    grupos_esperados = regras.get("grupos_esperados")
    if grupos_esperados is not None:
        esperado = {str(k): int(v) for k, v in grupos_esperados.items()}
        observado = dict(sorted(contagem_grupos.items()))
        if observado != dict(sorted(esperado.items())):
            raise ValueError(
                f"Distribuição de grupos territoriais inválida: observado={observado}, esperado={esperado}"
            )
    else:
        # Compatibilidade estrita com o contrato original TIC-TIM.
        internas = contagem_grupos.get("interna", 0)
        externas = contagem_grupos.get("externa", 0)
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
