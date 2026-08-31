from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ENV_DATA_ROOT = "TIC_TIM_DATA_ROOT"


@dataclass(frozen=True)
class Paths:
    project_root: Path
    data_root: Path
    raw: Path
    external: Path
    interim: Path
    processed: Path
    outputs: Path
    tables: Path
    maps: Path
    output_data: Path
    qa: Path
    reports: Path
    metadata: Path
    manifests: Path
    hashes: Path
    logs: Path
    cache: Path

    def create(self) -> None:
        for path in (
            self.raw,
            self.external,
            self.interim,
            self.processed,
            self.tables,
            self.maps,
            self.output_data,
            self.qa,
            self.reports,
            self.manifests,
            self.hashes,
            self.logs,
            self.cache,
        ):
            path.mkdir(parents=True, exist_ok=True)


def resolve_paths(project_root: Path) -> Paths:
    """Resolve todos os diretórios sem depender de usuário, máquina ou Drive."""
    project_root = project_root.resolve()
    configured = os.environ.get(ENV_DATA_ROOT)
    data_root = Path(configured).expanduser().resolve() if configured else project_root / "data"

    outputs = data_root / "outputs"
    metadata = data_root / "metadata"
    return Paths(
        project_root=project_root,
        data_root=data_root,
        raw=data_root / "raw",
        external=data_root / "external",
        interim=data_root / "interim",
        processed=data_root / "processed",
        outputs=outputs,
        tables=outputs / "tables",
        maps=outputs / "maps",
        output_data=outputs / "data",
        qa=outputs / "qa",
        reports=outputs / "reports",
        metadata=metadata,
        manifests=metadata / "manifests",
        hashes=metadata / "hashes",
        logs=metadata / "logs",
        cache=data_root / "cache",
    )
