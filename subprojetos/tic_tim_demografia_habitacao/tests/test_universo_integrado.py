from pathlib import Path

import pandas as pd

from tic_tim_demografia.universo_integrado import (
    G7E_FILENAME,
    _composicao_macrotipos,
    _detectar_linha_cabecalho,
    carregar_universo_integrado_canonico,
)


def test_detecta_cabecalho_apos_linhas_preambulares():
    preview = pd.DataFrame(
        [
            ["Gate 18G7E — validação ISAU × tipologia final", None, None],
            ["Nota metodológica", None, None],
            [None, None, None],
            ["CD_SETOR", "MACRO_FINAL", "ISAU_C3"],
            ["350000000000001", 2, 0.8],
        ]
    )
    assert _detectar_linha_cabecalho(preview) == 3


def test_carrega_aba_setorial_com_titulo_e_regra_semantica(tmp_path: Path):
    path = tmp_path / "checkpoints" / G7E_FILENAME
    path.parent.mkdir(parents=True)
    linhas = [
        ["Gate 18G7E — validação ISAU × tipologia final", None, None],
        ["Universo congelado para auditoria", None, None],
        [None, None, None],
        ["CD_SETOR", "MACRO_FINAL", "ISAU_C3"],
        ["350000000000001", 2, 0.80],
        ["350000000000002", 2, 0.70],
        ["350000000000003", 3, 0.90],
        ["350000000000004", 3, 0.60],
        ["350000000000005", 4, 0.50],
        ["350000000000006", 4, 0.40],
        ["350000000000007", 4, None],
        ["350000000000008", 5, 0.75],
    ]
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame([['README'], ['sem tabela setorial']]).to_excel(
            writer,
            sheet_name="00_LEIA_ME",
            header=False,
            index=False,
        )
        pd.DataFrame(linhas).to_excel(
            writer,
            sheet_name="02_BASE_SETORIAL",
            header=False,
            index=False,
        )

    universo, meta = carregar_universo_integrado_canonico(tmp_path, esperado=6)

    assert len(universo) == 6
    assert universo["codigo_setor"].nunique() == 6
    assert meta["aba_selecionada"] == "02_BASE_SETORIAL"
    assert meta["linha_cabecalho_excel_1based"] == 4
    assert meta["regra_selecao"] == "MACRO_FINAL in {2,3,4} + ISAU_C3 observado"


def test_composicao_macrotipos_ignora_outros_codigos():
    df = pd.DataFrame({"macrotipo_checkpoint": [2, 2, 3, 4, 4, 5, pd.NA]})
    assert _composicao_macrotipos(df) == {2: 2, 3: 1, 4: 2}
