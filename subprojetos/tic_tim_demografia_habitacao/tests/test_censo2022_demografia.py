import zipfile
from pathlib import Path

import pandas as pd
import pytest

from tic_tim_demografia.fontes.censo2022 import (
    agregar_demografia_2022_municipio,
    ler_demografia_setorial_zip,
    ler_setores_urbanos_basico_zip,
)


def _linha(setor: str, valores: dict[str, int]) -> dict[str, str]:
    linha = {"CD_SETOR": setor}
    for i in range(31, 42):
        linha[f"V010{i:02d}"] = str(valores.get(f"V010{i:02d}", 0))
    linha["V01006"] = str(sum(int(linha[f"V010{i:02d}"]) for i in range(31, 42)))
    return linha


def _zip_csv(
    tmp_path: Path,
    linhas: list[dict[str, str]],
    *,
    tema: str = "demografia",
    encoding: str = "utf-8",
) -> Path:
    csv = pd.DataFrame(linhas).to_csv(index=False, sep=";")
    path = tmp_path / f"{tema}.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(f"Agregados_por_setores_{tema}_BR.csv", csv.encode(encoding))
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
    assert mun["setores_idade_completa"] == 2
    assert mun["setores_idade_incompleta"] == 0


def test_basico_define_recorte_urbano_e_exclui_rural(tmp_path):
    basico = _zip_csv(
        tmp_path,
        [
            {"CD_SETOR": "350160805000001", "SITUACAO": "Urbana"},
            {"CD_SETOR": "350160805000002", "SITUACAO": "Rural"},
            {"CD_SETOR": "355030805000001", "SITUACAO": "Urbana"},
        ],
        tema="basico",
    )
    urbanos = ler_setores_urbanos_basico_zip(basico, codigos_municipais=["3501608"])
    assert urbanos["codigo_setor"].tolist() == ["350160805000001"]

    demografia = _zip_csv(
        tmp_path,
        [
            _linha("350160805000001", {"V01031": 10}),
            _linha("350160805000002", {"V01031": 999}),
        ],
    )
    setores = ler_demografia_setorial_zip(
        demografia,
        codigos_municipais=["3501608"],
        setores_permitidos=urbanos["codigo_setor"],
    )
    mun = agregar_demografia_2022_municipio(setores).iloc[0]
    assert mun["pop_total_fonte"] == 10


def test_basico_aceita_publicacao_cp1252(tmp_path):
    basico = _zip_csv(
        tmp_path,
        [{"CD_SETOR": "350160805000001", "SITUACAO": "Urbana", "OBS": "condição"}],
        tema="basico",
        encoding="cp1252",
    )
    urbanos = ler_setores_urbanos_basico_zip(basico, codigos_municipais=["3501608"])
    assert urbanos["codigo_setor"].tolist() == ["350160805000001"]


def test_sigilo_exclui_apenas_setor_incompleto_sem_imputar(tmp_path):
    completo = _linha("350160805000001", {"V01031": 10, "V01040": 5})
    protegido = _linha("350160805000002", {"V01031": 99, "V01040": 30})
    protegido["V01034"] = "X"
    protegido["V01006"] = "X"
    path = _zip_csv(tmp_path, [completo, protegido])
    setores = ler_demografia_setorial_zip(path, codigos_municipais=["3501608"])
    mun = agregar_demografia_2022_municipio(setores).iloc[0]

    assert mun["pop_total_harmonizada"] == 15
    assert mun["setores_demografia"] == 2
    assert mun["setores_idade_completa"] == 1
    assert mun["setores_idade_incompleta"] == 1
    assert mun["cobertura_setorial_idade"] == 0.5


def test_v01006_protegido_nao_elimina_setor_com_idades_completas(tmp_path):
    linha = _linha("350160805000001", {"V01031": 10, "V01040": 5})
    linha["V01006"] = "X"
    path = _zip_csv(tmp_path, [linha])
    setores = ler_demografia_setorial_zip(path, codigos_municipais=["3501608"])
    mun = agregar_demografia_2022_municipio(setores).iloc[0]
    assert mun["pop_total_harmonizada"] == 15
    assert mun["setores_idade_completa"] == 1


def test_simbolo_inesperado_bloqueia_agregacao(tmp_path):
    linha = _linha("350160805000001", {"V01031": 10})
    linha["V01031"] = ".."
    linha["V01006"] = "10"
    path = _zip_csv(tmp_path, [linha])
    setores = ler_demografia_setorial_zip(path, codigos_municipais=["3501608"])
    with pytest.raises(ValueError, match="não numéricos inesperados"):
        agregar_demografia_2022_municipio(setores)


def test_fechamento_setorial_bloqueia_divergencia_quando_comparavel(tmp_path):
    linha = _linha("350160805000001", {"V01031": 10, "V01040": 5})
    linha["V01006"] = "16"
    path = _zip_csv(tmp_path, [linha])
    setores = ler_demografia_setorial_zip(path, codigos_municipais=["3501608"])
    with pytest.raises(AssertionError, match="não fecham com V01006"):
        agregar_demografia_2022_municipio(setores)
