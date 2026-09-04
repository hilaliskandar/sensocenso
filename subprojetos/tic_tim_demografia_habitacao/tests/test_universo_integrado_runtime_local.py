from pathlib import Path

import pytest

from tic_tim_demografia import universo_integrado


def test_runtime_sem_checkpoint_nao_chama_loader_legacy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_root = tmp_path / "raw"

    def _falha_se_chamado(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("loader legado não pode ser chamado pelo runtime normal")

    monkeypatch.setattr(
        universo_integrado._legacy,
        "carregar_universo_integrado_canonico",
        _falha_se_chamado,
    )

    with pytest.raises(RuntimeError, match="runtime não faz download"):
        universo_integrado.carregar_universo_integrado_canonico(raw_root, esperado=4)
