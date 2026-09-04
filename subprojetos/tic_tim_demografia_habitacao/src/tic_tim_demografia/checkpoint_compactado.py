"""Leitura do payload versionado compacto do checkpoint Gate18G7F2.

O repositório armazena o CSV canônico compactado por gzip apenas para reduzir o
peso do artefato versionado. A identidade semântica continua sendo a do CSV
materializado historicamente: o SHA-256 registrado no manifesto é calculado
sobre os bytes descompactados.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
from pathlib import Path
from typing import Any

import pandas as pd

from .checkpoint_canonico import (
    CHECKPOINT_FILENAME,
    CHECKPOINT_ID,
    EXPECTED_INTEGRATED,
    MANIFEST_FILENAME,
    SELECTION_RULE,
    _macro_counts,
    _validar_frame,
)

COMPRESSED_FILENAME = f"{CHECKPOINT_FILENAME}.gz"


def caminho_payload_versionado() -> Path:
    """Retorna o payload compacto distribuído com o subprojeto."""
    projeto = Path(__file__).resolve().parents[2]
    return projeto / "data" / "checkpoints" / COMPRESSED_FILENAME


def carregar_checkpoint_compactado_versionado(
    *,
    esperado: int = EXPECTED_INTEGRATED,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Carrega e valida o checkpoint versionado sem qualquer acesso de rede."""
    payload = caminho_payload_versionado()
    manifest = payload.with_name(MANIFEST_FILENAME)
    if not payload.exists():
        raise RuntimeError(f"Payload compacto Gate18G7F2 ausente: {payload}")
    if not manifest.exists():
        raise RuntimeError(f"Manifesto do checkpoint canônico ausente: {manifest}")

    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    if metadata.get("checkpoint_id") != CHECKPOINT_ID:
        raise RuntimeError("Manifesto não identifica o checkpoint Gate18G7F2.")

    comprimido = payload.read_bytes()
    sha_gzip = hashlib.sha256(comprimido).hexdigest()
    esperado_gzip = metadata.get("sha256_payload_gzip")
    if esperado_gzip and esperado_gzip != sha_gzip:
        raise RuntimeError("SHA-256 do payload gzip diverge do manifesto.")

    bruto = gzip.decompress(comprimido)
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
        "fonte_checkpoint": str(payload),
        "papel": "checkpoint_canonico_versionado_compactado",
        "sha256_csv": sha_csv,
        "sha256_payload_gzip": sha_gzip,
        "regra_selecao": metadata.get("regra_selecao", SELECTION_RULE),
        "n_setores": len(canonico),
        "macro_composicao": counts,
        "download_runtime": False,
    }
    return canonico, diagnostico
