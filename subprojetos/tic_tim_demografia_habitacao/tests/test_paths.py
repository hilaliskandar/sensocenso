from pathlib import Path

from tic_tim_demografia.paths import ENV_DATA_ROOT, resolve_paths


def test_data_root_padrao_e_relativo_ao_subprojeto(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv(ENV_DATA_ROOT, raising=False)
    paths = resolve_paths(tmp_path)
    assert paths.data_root == tmp_path.resolve() / "data"
    assert paths.raw == paths.data_root / "raw"
    assert paths.processed == paths.data_root / "processed"
    assert paths.outputs == paths.data_root / "outputs"
    assert paths.manifests == paths.data_root / "metadata" / "manifests"


def test_data_root_pode_ser_externalizado_sem_mudar_codigo(tmp_path: Path, monkeypatch) -> None:
    externo = tmp_path / "volume" / "dados_tic_tim"
    monkeypatch.setenv(ENV_DATA_ROOT, str(externo))
    paths = resolve_paths(tmp_path / "repositorio")
    assert paths.data_root == externo.resolve()
    assert paths.maps == externo.resolve() / "outputs" / "maps"


def test_paths_nao_contem_dependencia_drive_ou_usuario(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv(ENV_DATA_ROOT, raising=False)
    paths = resolve_paths(tmp_path)
    serializado = "\n".join(str(v) for v in paths.__dict__.values()).lower()
    assert "mydrive" not in serializado
    assert "google drive" not in serializado
    assert "/content/drive" not in serializado
