"""Leitura do payload versionado compacto do checkpoint Gate18G7F2.

O CSV canônico é compactado por gzip e armazenado no repositório como partes
Base64 de texto. Essa representação evita dependência de binários no mecanismo
de atualização do repositório; a identidade semântica continua sendo a dos
bytes do CSV descompactado, verificados por SHA-256.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import io
import json
from pathlib import Path
from typing import Any

import pandas as pd

from .checkpoint_canonico import (
    CHECKPOINT_ID,
    EXPECTED_INTEGRATED,
    MANIFEST_FILENAME,
    SELECTION_RULE,
    _macro_counts,
    _validar_frame,
)

PARTS_DIRNAME = "payload_g7f2_b64"
PUBLIC_CHECKPOINT_SOURCE = f"data/checkpoints/{PARTS_DIRNAME}"


def caminho_payload_versionado() -> Path:
    """Retorna o diretório das partes Base64 distribuídas com o subprojeto."""
    projeto = Path(__file__).resolve().parents[2]
    return projeto / "data" / "checkpoints" / PARTS_DIRNAME


def carregar_checkpoint_compactado_versionado(
    *,
    esperado: int = EXPECTED_INTEGRATED,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Carrega e valida o checkpoint versionado sem qualquer acesso de rede."""
    parts_dir = caminho_payload_versionado()
    manifest = parts_dir.parent / MANIFEST_FILENAME
    partes = sorted(parts_dir.glob("part-*.b64")) if parts_dir.exists() else []
    if not partes:
        raise RuntimeError(f"Partes Base64 do Gate18G7F2 ausentes: {parts_dir}")
    if not manifest.exists():
        raise RuntimeError(f"Manifesto do checkpoint canônico ausente: {manifest}")

    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    if metadata.get("checkpoint_id") != CHECKPOINT_ID:
        raise RuntimeError("Manifesto não identifica o checkpoint Gate18G7F2.")
    esperado_partes = int(metadata.get("n_partes", len(partes)))
    if len(partes) != esperado_partes:
        raise RuntimeError(
            f"Quantidade de partes Base64 divergente: {len(partes)} != {esperado_partes}."
        )

    texto_b64 = "".join(p.read_text(encoding="ascii").strip() for p in partes)
    try:
        comprimido = base64.b64decode(texto_b64, validate=True)
    except ValueError as exc:
        raise RuntimeError("Payload Base64 do Gate18G7F2 é inválido.") from exc

    sha_gzip = hashlib.sha256(comprimido).hexdigest()
    esperado_gzip = metadata.get("sha256_payload_gzip")
    if esperado_gzip and esperado_gzip != sha_gzip:
        raise RuntimeError("SHA-256 do payload gzip reconstruído diverge do manifesto.")
    try:
        bruto = gzip.decompress(comprimido)
    except (OSError, EOFError) as exc:
        raise RuntimeError("Payload gzip do Gate18G7F2 é inválido ou está truncado.") from exc

    sha_csv = hashlib.sha256(bruto).hexdigest()
    if metadata.get("sha256_csv") != sha_csv:
        raise RuntimeError(
            "SHA-256 do CSV descompactado diverge do manifesto; payload pode ter sido alterado."
        )

    frame = pd.read_csv(io.BytesIO(bruto), dtype={"codigo_setor": "string"})
    canonico = _validar_frame(frame, esperado)
    counts = _macro_counts(canonico)
    manifesto_counts = {
        int(key): int(value) for key, value in metadata.get("macro_composicao", {}).items()
    }
    if int(metadata.get("n_setores", -1)) != len(canonico) or manifesto_counts != counts:
        raise RuntimeError("Cardinalidade ou composição do manifesto diverge do payload canônico.")

    diagnostico: dict[str, Any] = {
        "status": "ok",
        "checkpoint_id": CHECKPOINT_ID,
        "fonte_checkpoint": PUBLIC_CHECKPOINT_SOURCE,
        "papel": "checkpoint_canonico_versionado_compactado",
        "formato_versionado": "gzip-base64-partes",
        "n_partes": len(partes),
        "sha256_csv": sha_csv,
        "sha256_payload_gzip": sha_gzip,
        "regra_selecao": metadata.get("regra_selecao", SELECTION_RULE),
        "n_setores": len(canonico),
        "macro_composicao": counts,
        "download_runtime": False,
    }
    return canonico, diagnostico
