from pathlib import Path

import pytest

from tic_tim_demografia import universo_integrado


def test_runtime_versionado_nao_chama_loader_legacy(
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

    frame, diagnostico = universo_integrado.carregar_universo_integrado_canonico(raw_root)

    assert len(frame) == 8073
    assert frame["codigo_setor"].nunique() == 8073
    assert frame["macrotipo_checkpoint"].value_counts().to_dict() == {3: 3843, 2: 3568, 4: 662}
    assert diagnostico["checkpoint_id"] == "Gate18G7F2"
    assert diagnostico["download_runtime"] is False
    assert diagnostico["papel"] == "checkpoint_canonico_versionado_compactado"
