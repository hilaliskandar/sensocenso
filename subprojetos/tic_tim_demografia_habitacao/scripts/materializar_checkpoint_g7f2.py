#!/usr/bin/env python3
"""Materializa o checkpoint canônico Gate18G7F2 a partir de fonte histórica local."""

from __future__ import annotations

import argparse
from pathlib import Path

from tic_tim_demografia.checkpoint_canonico import materializar_checkpoint_de_fonte


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Materializa o universo integrado canônico TIC–TIM sem dependência de rede no runtime."
        )
    )
    parser.add_argument(
        "--fonte",
        required=True,
        type=Path,
        help="Fonte histórica auditada (.gpkg, .xlsx, .csv ou .parquet).",
    )
    parser.add_argument(
        "--sheet",
        default=None,
        help="Aba XLSX, se for necessário fixá-la explicitamente.",
    )
    parser.add_argument(
        "--destino",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "checkpoints",
        help="Diretório de saída do CSV canônico e de seu manifesto.",
    )
    args = parser.parse_args()

    checkpoint, manifest = materializar_checkpoint_de_fonte(
        args.fonte,
        args.destino,
        sheet=args.sheet,
    )
    print(f"Checkpoint: {checkpoint}")
    print(f"Manifesto: {manifest}")


if __name__ == "__main__":
    main()
