import zipfile
from pathlib import Path

import pandas as pd
import pytest

from tic_tim_demografia.fontes.censo2022 import (
    agregar_demografia_2022_municipio,
    ler_demografia_setorial_zip,
)


def _linha(setor: str, valores: dict[str, int]) -> dict[str, str]:
    linha = {"CD_SETOR": setor}
    for i in range(31, 42):
        linha[f"V010{i:02d}"] = str(valores.get(f"V010{i:02d}", 0))
    linha["V01006"] = str(sum(int(linha[f"V010{i:02d}"]) for i in range(31, 42)))
    return linha


def _zip_csv(tmp_path: Path, linhas: list[dict[str, str]]) -> Path:
    csv = pd.DataFrame(linhas).to_csv(index=False, sep=";")
    path = tmp_path / "demografia.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("Agregados_por_setores_demografia_BR.csv", csv.encode("utf-8"))
    return path


def test_recorta_por_codigo_municipal_e_agrega_bandas(tmp_path):
    a = _linha(
        "350160805000001",
        {"V01031": 10, "V01032": 11, "V01033": 12, "V01034": 13, "V01035": 14,
         "V01036": 15, "V01037": 16, "V01038": 17, "V01039": 18, "V01040": 19, "V01041": 20},
    )
    b = _linha(
        "350160805000002",
        {"V01031": 1, "V01032": 2, "V01033": 3, "V01034": 4, "V01035": 5,
         "V01036": 6, "V01037": 7, "V01038": 8, "V01039": 9, "V01040": 10, "V01041": 11},
    )
    fora = _linha("355030805000001", {"V01031": 999})
    path = _zip_csv(tmp_path, [a, b, fora])

    setores = ler_demografia_setorial_zip(path, codigos_municipais=["3501608"])
    assert len(setores) == 2
    mun = agregar_demografia_2022_municipio(setores).iloc[0]
    assert mun["pop_0_14"] == 39
    assert mun["pop_15_59"] == 132
    assert mun["pop_60_mais"] == 60
    assert mun["pop_total_harmonizada"] == 231
    assert mun["pop_total_fonte"] == 231
    assert mun["diferenca_fechamento"] == 0


def test_valor_especial_bloqueia_agregacao(tmp_path):
    linha = _linha("350160805000001", {"V01031": 10})
    linha["V01031"] = ".."
    linha["V01006"] = "10"
    path = _zip_csv(tmp_path, [linha])
    setores = ler_demografia_setorial_zip(path, codigos_municipais=["3501608"])
    with pytest.raises(ValueError, match="não numéricos"):
        agregar_demografia_2022_municipio(setores)


def test_fechamento_interno_bloqueia_divergencia(tmp_path):
    linha = _linha("350160805000001", {"V01031": 10, "V01040": 5})
    linha["V01006"] = "16"
    path = _zip_csv(tmp_path, [linha])
    setores = ler_demografia_setorial_zip(path, codigos_municipais=["3501608"])
    with pytest.raises(AssertionError, match="não fecham"):
        agregar_demografia_2022_municipio(setores)
