import json
from pathlib import Path

import pandas as pd
import pytest

from tic_tim_demografia.checkpoint_canonico import (
    CHECKPOINT_FILENAME,
    DIAGNOSTIC_FILENAME,
    MANIFEST_FILENAME,
    carregar_checkpoint_canonico_local,
    escrever_checkpoint_canonico,
    materializar_checkpoint_de_fonte,
)


def _canonico_sintetico() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "codigo_setor": [
                "350000000000001",
                "350000000000002",
                "350000000000003",
                "350000000000004",
            ],
            "macrotipo_checkpoint": [2, 3, 4, 2],
        }
    )


def test_checkpoint_local_valida_hash_manifesto_e_cardinalidade(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    destino = raw_root / "checkpoints"
    escrever_checkpoint_canonico(
        _canonico_sintetico(), destino, esperado=4, fonte="teste.csv"
    )

    frame, diag = carregar_checkpoint_canonico_local(raw_root, esperado=4)

    assert len(frame) == 4
    assert diag["status"] == "ok"
    assert diag["download_runtime"] is False
    assert diag["macro_composicao"] == {2: 2, 3: 1, 4: 1}
    assert (destino / DIAGNOSTIC_FILENAME).exists()


def test_checkpoint_local_rejeita_csv_adulterado(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    destino = raw_root / "checkpoints"
    checkpoint, _ = escrever_checkpoint_canonico(
        _canonico_sintetico(), destino, esperado=4, fonte="teste.csv"
    )
    checkpoint.write_text(checkpoint.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="SHA-256"):
        carregar_checkpoint_canonico_local(raw_root, esperado=4)


def test_checkpoint_ausente_falha_sem_tentar_download(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"

    with pytest.raises(RuntimeError, match="runtime não faz download"):
        carregar_checkpoint_canonico_local(raw_root, esperado=4)

    diag_path = raw_root / "checkpoints" / DIAGNOSTIC_FILENAME
    diag = json.loads(diag_path.read_text(encoding="utf-8"))
    assert diag["erro"] == "checkpoint_canonico_local_ausente"
    assert diag["esperado"] == 4


def test_materializacao_aplica_regra_semantica(tmp_path: Path) -> None:
    fonte = tmp_path / "fonte.csv"
    pd.DataFrame(
        {
            "CD_SETOR": [
                "350000000000001",
                "350000000000002",
                "350000000000003",
                "350000000000004",
                "350000000000005",
            ],
            "MACRO_FINAL": [2, 3, 4, 2, 3],
            "ISAU_C3": [0.7, 0.8, 0.9, 1.0, None],
        }
    ).to_csv(fonte, index=False)
    destino = tmp_path / "checkpoint"

    checkpoint, manifest = materializar_checkpoint_de_fonte(
        fonte, destino, esperado=4
    )

    assert checkpoint.name == CHECKPOINT_FILENAME
    assert manifest.name == MANIFEST_FILENAME
    frame = pd.read_csv(checkpoint, dtype={"codigo_setor": "string"})
    assert frame["codigo_setor"].tolist() == [
        "350000000000001",
        "350000000000002",
        "350000000000003",
        "350000000000004",
    ]
    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    assert metadata["regra_selecao"] == "MACRO_FINAL in {2,3,4} AND ISAU_C3 not null"
    assert metadata["n_setores"] == 4


def test_manifesto_divergente_e_rejeitado(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    destino = raw_root / "checkpoints"
    _, manifest = escrever_checkpoint_canonico(
        _canonico_sintetico(), destino, esperado=4, fonte="teste.csv"
    )
    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    metadata["n_setores"] = 5
    manifest.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(RuntimeError, match="Cardinalidade ou composição"):
        carregar_checkpoint_canonico_local(raw_root, esperado=4)
