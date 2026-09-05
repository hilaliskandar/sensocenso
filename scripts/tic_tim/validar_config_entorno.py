#!/usr/bin/env python3
"""Validação estática das regras E01–E10 do Entorno.

Não lê dados censitários. Verifica apenas a integridade estrutural da configuração
antes da execução sobre o DBF canônico.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

EXPECTED = {
    "E01": ("01", "02", "03", "04", "05"),
    "E02": ("06", "07", "08"),
    "E03": ("09", "10", "11"),
    "E04": ("12", "13", "14"),
    "E05": ("15", "16", "17"),
    "E06": ("18", "19", "20"),
    "E07": ("21", "22", "23"),
    "E08": ("24", "25", "26"),
    "E09": ("27", "28", "29"),
    "E10": ("30", "31", "32", "33", "34"),
}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=Path("config/tic_tim_entorno_regras.json"))
    args = p.parse_args()

    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    erros: list[str] = []

    if cfg.get("universos") != {
        "V050": "Domicílios",
        "V052": "Moradores",
        "V054": "Faces",
    }:
        erros.append("universos divergentes de V050/V052/V054")

    tabelas = cfg.get("tabelas", {})
    if set(tabelas) != set(EXPECTED):
        erros.append("conjunto de tabelas deve ser exatamente E01-E10")

    vistos: list[str] = []
    for tabela, sufixos_esperados in EXPECTED.items():
        spec = tabelas.get(tabela, {})
        cats = spec.get("categorias", [])
        sufixos = tuple(str(c.get("sufixo", "")) for c in cats)
        if sufixos != sufixos_esperados:
            erros.append(f"{tabela}: sufixos {sufixos} != {sufixos_esperados}")
        if not spec.get("nome") or not spec.get("regra_dominio"):
            erros.append(f"{tabela}: nome/regra_dominio ausente")
        for c in cats:
            if not isinstance(c.get("aplicavel"), bool):
                erros.append(f"{tabela}/{c.get('sufixo')}: aplicavel deve ser booleano")
            if not c.get("categoria"):
                erros.append(f"{tabela}/{c.get('sufixo')}: categoria vazia")
            vistos.append(str(c.get("sufixo", "")))

    esperados = [f"{i:02d}" for i in range(1, 35)]
    if vistos != esperados:
        erros.append(f"sequência global de sufixos deve ser 01-34; obtida={vistos}")

    if erros:
        raise SystemExit("FAIL: " + " | ".join(erros))

    print("PASS tabelas=10 universos=3 sufixos=34")


if __name__ == "__main__":
    main()
