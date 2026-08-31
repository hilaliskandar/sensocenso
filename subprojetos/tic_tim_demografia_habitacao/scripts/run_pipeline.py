#!/usr/bin/env python3
"""Orquestrador do pipeline TIC–TIM de demografia e habitação.

As etapas são implementadas incrementalmente. Uma etapa só deixa o estado de
placeholder depois de possuir fonte, proveniência, QA e testes compatíveis com
o caderno metodológico público.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tic_tim_demografia import (  # noqa: E402
    etapa00,
    etapa01,
    etapa02,
    etapa02b,
    etapa02c,
    etapa03a,
    etapa03b,
    etapa03c,
    etapa04,
    etapa05a,
)


@dataclass(frozen=True)
class Etapa:
    codigo: str
    nome: str
    funcao: Callable[[Path], None]
    implementada: bool = True


def ainda_nao_implementada(nome: str) -> Callable[[Path], None]:
    def executar(_raiz: Path) -> None:
        raise NotImplementedError(
            f"Etapa '{nome}' ainda não implementada. "
            "A implementação deve reproduzir o caderno metodológico e passar pelos testes de regressão."
        )

    return executar


ETAPAS = [
    Etapa("00", "configuração, universo e QA inicial", etapa00.executar),
    Etapa("01", "aquisição e congelamento inicial das fontes", etapa01.executar),
    Etapa("02a", "gate semântico SIDRA para harmonização longitudinal", etapa02.executar),
    Etapa("02b", "coleta e harmonização longitudinal 2000–2010", etapa02b.executar),
    Etapa("02c", "agregação urbana 2022 e fechamento longitudinal 30×3", etapa02c.executar),
    Etapa("03a", "gate semântico e descoberta das fontes domiciliares", etapa03a.executar),
    Etapa("03b", "base domiciliar histórica 2000–2010", etapa03b.executar),
    Etapa("03c", "domicílios 2022 e integração temporal", etapa03c.executar),
    Etapa("04", "renovação demográfica recente (CWR)", etapa04.executar),
    Etapa("05a", "gate semântico e descoberta das fontes do ISAU", etapa05a.executar),
    Etapa("05b", "ISAU e privação sanitário-ambiental", ainda_nao_implementada("ISAU e privação sanitário-ambiental"), False),
    Etapa("06", "entorno urbano", ainda_nao_implementada("entorno urbano"), False),
    Etapa("07", "famílias analíticas", ainda_nao_implementada("famílias analíticas"), False),
    Etapa("08", "sensibilidade P75/P80", ainda_nao_implementada("sensibilidade P75/P80"), False),
    Etapa("09", "validação espacial", ainda_nao_implementada("validação espacial"), False),
    Etapa("10", "sínteses municipais", ainda_nao_implementada("sínteses municipais"), False),
    Etapa("11", "tabelas e mapas", ainda_nao_implementada("tabelas e mapas"), False),
    Etapa("12", "QA final", ainda_nao_implementada("QA final"), False),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raiz", type=Path, default=ROOT)
    parser.add_argument(
        "--etapa",
        choices=[e.codigo for e in ETAPAS] + ["implementadas", "todas"],
        default="implementadas",
    )
    parser.add_argument("--listar", action="store_true")
    args = parser.parse_args()

    if args.listar:
        for etapa in ETAPAS:
            status = "OK" if etapa.implementada else "PENDENTE"
            print(f"{etapa.codigo}: {etapa.nome} [{status}]")
        return

    if args.etapa == "implementadas":
        selecionadas = [e for e in ETAPAS if e.implementada]
    elif args.etapa == "todas":
        selecionadas = ETAPAS
    else:
        selecionadas = [e for e in ETAPAS if e.codigo == args.etapa]

    for etapa in selecionadas:
        print(f"[{etapa.codigo}] {etapa.nome}")
        etapa.funcao(args.raiz)


if __name__ == "__main__":
    main()
