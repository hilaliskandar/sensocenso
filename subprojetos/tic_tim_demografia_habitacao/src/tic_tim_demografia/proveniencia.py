from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_arquivo(path: Path, bloco: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(bloco), b""):
            h.update(chunk)
    return h.hexdigest()


def registrar_evento(manifesto: Path, evento: dict[str, Any]) -> None:
    manifesto.parent.mkdir(parents=True, exist_ok=True)
    registro = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        **evento,
    }
    with manifesto.open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False, sort_keys=True) + "\n")


def registrar_arquivo(manifesto: Path, path: Path, *, origem: str | None = None) -> dict[str, Any]:
    registro = {
        "tipo": "arquivo",
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_arquivo(path),
        "origem": origem,
    }
    registrar_evento(manifesto, registro)
    return registro
