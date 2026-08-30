#!/usr/bin/env python3
"""Orquestrador do pipeline TIC–TIM de demografia e habitação.

Nesta primeira versão o script define o contrato das etapas. Cada módulo será
implementado e validado contra os produtos auditados antes de a etapa seguinte
ser considerada estável.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class Etapa:
    codigo: str
    nome: str
    funcao: Callable[[Path], None]


def ainda_nao_implementada(nome: str) -> Callable[[Path], None]:
    def executar(_raiz: Path) -> None:
        raise NotImplementedError(
            f"Etapa '{nome}' ainda não implementada. "
            "A implementação deve reproduzir o caderno metodológico e passar pelos testes de regressão."
        )

    return executar


ETAPAS = [
    Etapa("01", "aquisição das fontes", ainda_nao_implementada("aquisição das fontes")),
    Etapa("02", "harmonização longitudinal", ainda_nao_implementada("harmonização longitudinal")),
    Etapa("03", "indicadores domiciliares", ainda_nao_implementada("indicadores domiciliares")),
    Etapa("04", "CWR", ainda_nao_implementada("CWR")),
    Etapa("05", "ISAU e privação", ainda_nao_implementada("ISAU e privação")),
    Etapa("06", "entorno urbano", ainda_nao_implementada("entorno urbano")),
    Etapa("07", "famílias analíticas", ainda_nao_implementada("famílias analíticas")),
    Etapa("08", "sensibilidade P75/P80", ainda_nao_implementada("sensibilidade P75/P80")),
    Etapa("09", "validação espacial", ainda_nao_implementada("validação espacial")),
    Etapa("10", "sínteses municipais", ainda_nao_implementada("sínteses municipais")),
    Etapa("11", "tabelas e mapas", ainda_nao_implementada("tabelas e mapas")),
    Etapa("12", "QA final", ainda_nao_implementada("QA final")),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raiz", type=Path, default=Path.cwd())
    parser.add_argument("--etapa", choices=[e.codigo for e in ETAPAS] + ["todas"], default="todas")
    parser.add_argument("--listar", action="store_true")
    args = parser.parse_args()

    if args.listar:
        for etapa in ETAPAS:
            print(f"{etapa.codigo}: {etapa.nome}")
        return

    selecionadas = ETAPAS if args.etapa == "todas" else [e for e in ETAPAS if e.codigo == args.etapa]
    for etapa in selecionadas:
        print(f"[{etapa.codigo}] {etapa.nome}")
        etapa.funcao(args.raiz)


if __name__ == "__main__":
    main()
