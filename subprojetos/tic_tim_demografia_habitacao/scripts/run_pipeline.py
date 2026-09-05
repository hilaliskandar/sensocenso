#!/usr/bin/env python3
"""Orquestrador do pipeline TIC–TIM de demografia e habitação.

As etapas são implementadas incrementalmente. Nas etapas 07–11e existem modos
explícitos: ``corrente`` usa fontes públicas atuais com checkpoint territorial
histórico imutável quando necessário e registra deriva de edição;
``historico`` mantém os gates numéricos rígidos do fechamento original.
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
    etapa00, etapa01, etapa02, etapa02b, etapa02c, etapa03a, etapa03b, etapa03c,
    etapa04, etapa05a, etapa05b, etapa05c, etapa05d, etapa05e, etapa06a, etapa06b,
    etapa07, etapa07_corrente, etapa08, etapa08_corrente, etapa09, etapa09_corrente,
    etapa10_corrente, etapa10b_corrente, etapa11a_tabelas, etapa11b_graficos,
    etapa11c_cartografia_municipal, etapa11d_cartografia_setorial,
    etapa11e_manifesto_visual,
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
            f"Etapa '{nome}' ainda não implementada. A implementação deve reproduzir o caderno metodológico e passar pelos testes de regressão."
        )
    return executar


ETAPAS_BASE = [
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
    Etapa("05b", "inspeção de arquivos e variáveis do ISAU", etapa05b.executar),
    Etapa("05c", "cálculo do ISAU C3/C4 e privação", etapa05c.executar),
    Etapa("05d", "estrutura dimensional do ISAU corrigido", etapa05d.executar),
    Etapa("05e", "ponderação por exposição e priorização do ISAU corrigido", etapa05e.executar),
    Etapa("06a", "gate semântico dos atributos do entorno urbano", etapa06a.executar),
    Etapa("06b", "atributos setoriais do entorno e F3", etapa06b.executar),
]
ETAPAS_FINAIS = [
    Etapa("11", "conjunto completo de tabelas, gráficos e mapas", ainda_nao_implementada("conjunto completo de tabelas, gráficos e mapas"), False),
    Etapa("12", "QA final", ainda_nao_implementada("QA final"), False),
]


def etapas_para_modo(modo: str) -> list[Etapa]:
    if modo == "historico":
        analiticas = [
            Etapa("07", "quatro famílias analíticas P75 — regressão histórica", etapa07.executar),
            Etapa("08", "sensibilidade P75/P80 — regressão histórica", etapa08.executar),
            Etapa("09", "validação espacial — regressão histórica", etapa09.executar),
            Etapa(
                "10",
                "sínteses municipais — regressão histórica",
                ainda_nao_implementada("sínteses municipais — regressão histórica"),
                False,
            ),
            Etapa(
                "10b",
                "camadas distributivas — regressão histórica",
                ainda_nao_implementada("camadas distributivas — regressão histórica"),
                False,
            ),
            Etapa(
                "11a",
                "tabelas públicas — regressão histórica",
                ainda_nao_implementada("tabelas públicas — regressão histórica"),
                False,
            ),
            Etapa(
                "11b",
                "gráficos públicos — regressão histórica",
                ainda_nao_implementada("gráficos públicos — regressão histórica"),
                False,
            ),
            Etapa(
                "11c",
                "cartografia municipal — regressão histórica",
                ainda_nao_implementada("cartografia municipal — regressão histórica"),
                False,
            ),
            Etapa(
                "11d",
                "cartografia setorial e entorno — regressão histórica",
                ainda_nao_implementada("cartografia setorial e entorno — regressão histórica"),
                False,
            ),
            Etapa(
                "11e",
                "manifesto visual e QA de cobertura — regressão histórica",
                ainda_nao_implementada("manifesto visual e QA de cobertura — regressão histórica"),
                False,
            ),
        ]
    else:
        analiticas = [
            Etapa("07", "quatro famílias P75 — fontes correntes + checkpoint histórico", etapa07_corrente.executar),
            Etapa("08", "sensibilidade P75/P80 — fontes correntes + checkpoint histórico", etapa08_corrente.executar),
            Etapa("09", "validação espacial — fontes correntes + checkpoint histórico", etapa09_corrente.executar),
            Etapa("10", "sínteses municipais e correlações — fontes correntes", etapa10_corrente.executar),
            Etapa("10b", "camadas distributivas raça/cor, FCU e arranjo doméstico — fontes correntes", etapa10b_corrente.executar),
            Etapa("11a", "tabelas públicas reprodutíveis — fontes correntes", etapa11a_tabelas.executar),
            Etapa("11b", "gráficos públicos reprodutíveis — fontes correntes", etapa11b_graficos.executar),
            Etapa("11c", "cartografia municipal reprodutível — fontes correntes", etapa11c_cartografia_municipal.executar),
            Etapa("11d", "cartografia setorial e prancha do entorno — fontes correntes", etapa11d_cartografia_setorial.executar),
            Etapa("11e", "manifesto visual e QA de cobertura — fontes correntes", etapa11e_manifesto_visual.executar),
        ]
    return ETAPAS_BASE + analiticas + ETAPAS_FINAIS


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raiz", type=Path, default=ROOT)
    parser.add_argument(
        "--modo", choices=["corrente", "historico"], default="corrente",
        help=(
            "corrente: recalcula variáveis com fontes públicas atuais e registra deriva; "
            "historico: exige regressão numérica integral do fechamento original"
        ),
    )
    codigos = [e.codigo for e in ETAPAS_BASE + ETAPAS_FINAIS] + ["07", "08", "09", "10", "10b", "11a", "11b", "11c", "11d", "11e"]
    parser.add_argument("--etapa", choices=sorted(set(codigos)) + ["implementadas", "todas"], default="implementadas")
    parser.add_argument("--listar", action="store_true")
    args = parser.parse_args()

    etapas = etapas_para_modo(args.modo)
    if args.listar:
        print(f"modo: {args.modo}")
        for etapa in etapas:
            print(f"{etapa.codigo}: {etapa.nome} [{'OK' if etapa.implementada else 'PENDENTE'}]")
        return
    if args.etapa == "implementadas":
        selecionadas = [e for e in etapas if e.implementada]
    elif args.etapa == "todas":
        selecionadas = etapas
    else:
        selecionadas = [e for e in etapas if e.codigo == args.etapa]
    for etapa in selecionadas:
        print(f"[{etapa.codigo}] {etapa.nome} (modo={args.modo})")
        etapa.funcao(args.raiz)


if __name__ == "__main__":
    main()
