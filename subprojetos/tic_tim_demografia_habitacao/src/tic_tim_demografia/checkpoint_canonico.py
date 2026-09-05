"""Checkpoint canônico local do universo integrado TIC–TIM.

O runtime não acessa Google Sheets. A identidade dos 8.073 setores é materializada
uma única vez a partir de uma fonte histórica auditada e, depois, validada por hash,
esquema, cardinalidade e composição de macrotipos.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd

CHECKPOINT_ID = "Gate18G7F2"
CHECKPOINT_FILENAME = "TIC_TIM_UNIVERSO_INTEGRADO_CANONICO_G7F2.csv"
MANIFEST_FILENAME = "TIC_TIM_UNIVERSO_INTEGRADO_CANONICO_G7F2.manifest.json"
DIAGNOSTIC_FILENAME = "TIC_TIM_GATE18G7E_diagnostico.json"
EXPECTED_INTEGRATED = 8073
EXPECTED_MACRO_COUNTS = {2: 3568, 3: 3843, 4: 662}
SELECTION_RULE = "MACRO_FINAL in {2,3,4} AND ISAU_C3 not null"

SECTOR_ALIASES = ("CDSETOR", "CDSETOR2022", "CODIGOSETOR", "CODSETOR")
MACRO_ALIASES = ("MACROFINAL", "MACROTIPOFINAL", "MACROG6", "MACROTIPO", "MACRO")
ISAU_ALIASES = ("ISAUC3", "ISAUC3FINAL")


def _normalizar_nome(valor: object) -> str:
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(char for char in texto if not unicodedata.combining(char))
    return re.sub(r"[^A-Z0-9]+", "", texto.upper())


def _normalizar_codigo(valor: object) -> str | None:
    if pd.isna(valor):
        return None
    if isinstance(valor, int):
        texto = str(valor)
    elif isinstance(valor, float) and valor.is_integer():
        texto = str(int(valor))
    else:
        texto = str(valor).strip()
        if texto.endswith(".0") and texto[:-2].isdigit():
            texto = texto[:-2]
    return texto if re.fullmatch(r"\d{15}", texto) else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for bloco in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _macro_counts(frame: pd.DataFrame) -> dict[int, int]:
    counts = frame["macrotipo_checkpoint"].value_counts().sort_index()
    return {int(macro): int(counts.get(macro, 0)) for macro in (2, 3, 4)}


def _validar_frame(frame: pd.DataFrame, esperado: int) -> pd.DataFrame:
    faltantes = {"codigo_setor", "macrotipo_checkpoint"} - set(frame.columns)
    if faltantes:
        raise RuntimeError(f"Checkpoint canônico sem colunas obrigatórias: {sorted(faltantes)}")

    saida = frame[["codigo_setor", "macrotipo_checkpoint"]].copy()
    saida["codigo_setor"] = saida["codigo_setor"].map(_normalizar_codigo)
    if saida["codigo_setor"].isna().any():
        raise RuntimeError("Checkpoint canônico contém código de setor inválido; esperado 15 dígitos.")

    saida["macrotipo_checkpoint"] = pd.to_numeric(
        saida["macrotipo_checkpoint"], errors="coerce"
    )
    if saida["macrotipo_checkpoint"].isna().any():
        raise RuntimeError("Checkpoint canônico contém macrotipo não numérico.")
    saida["macrotipo_checkpoint"] = saida["macrotipo_checkpoint"].astype(int)

    macros_invalidos = sorted(set(saida["macrotipo_checkpoint"]) - {2, 3, 4})
    if macros_invalidos:
        raise RuntimeError(f"Checkpoint canônico contém macrotipos inválidos: {macros_invalidos}")
    if saida["codigo_setor"].duplicated().any():
        duplicados = int(saida["codigo_setor"].duplicated(keep=False).sum())
        raise RuntimeError(f"Checkpoint canônico contém {duplicados} linhas com setores duplicados.")
    if len(saida) != esperado:
        raise RuntimeError(
            f"Checkpoint canônico tem {len(saida)} setores; esperado {esperado}."
        )

    counts = _macro_counts(saida)
    if esperado == EXPECTED_INTEGRATED and counts != EXPECTED_MACRO_COUNTS:
        raise RuntimeError(
            "Composição de macrotipos diverge do Gate18G7F2: "
            f"observado={counts}; esperado={EXPECTED_MACRO_COUNTS}."
        )

    return saida.sort_values("codigo_setor").reset_index(drop=True)


def _escrever_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def escrever_checkpoint_canonico(
    frame: pd.DataFrame,
    destino: str | Path,
    *,
    esperado: int = EXPECTED_INTEGRATED,
    fonte: str,
) -> tuple[Path, Path]:
    """Grava CSV determinístico e manifesto auditável do checkpoint."""
    destino_path = Path(destino)
    destino_path.mkdir(parents=True, exist_ok=True)
    checkpoint = destino_path / CHECKPOINT_FILENAME
    manifest = destino_path / MANIFEST_FILENAME

    canonico = _validar_frame(frame, esperado)
    canonico.to_csv(checkpoint, index=False, lineterminator="\n")
    sha = _sha256(checkpoint)
    counts = _macro_counts(canonico)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "checkpoint_id": CHECKPOINT_ID,
        "fonte_materializacao": fonte,
        "regra_selecao": SELECTION_RULE,
        "arquivo": CHECKPOINT_FILENAME,
        "sha256_csv": sha,
        "n_setores": len(canonico),
        "macro_composicao": {str(key): value for key, value in counts.items()},
        "colunas": ["codigo_setor", "macrotipo_checkpoint"],
    }
    _escrever_json(manifest, payload)
    return checkpoint, manifest


def _candidatos(raw_root: Path) -> list[Path]:
    projeto = Path(__file__).resolve().parents[2]
    return [
        raw_root / "checkpoints" / CHECKPOINT_FILENAME,
        projeto / "data" / "checkpoints" / CHECKPOINT_FILENAME,
    ]


def carregar_checkpoint_canonico_local(
    raw_root: str | Path,
    *,
    esperado: int = EXPECTED_INTEGRATED,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Carrega apenas checkpoint local e falha cedo se ele não estiver materializado."""
    raw_path = Path(raw_root)
    candidatos = _candidatos(raw_path)
    diagnostico_path = raw_path / "checkpoints" / DIAGNOSTIC_FILENAME
    checkpoint = next((path for path in candidatos if path.exists()), None)
    if checkpoint is None:
        diagnostico = {
            "status": "erro",
            "erro": "checkpoint_canonico_local_ausente",
            "checkpoint_id": CHECKPOINT_ID,
            "candidatos": [str(path) for path in candidatos],
            "regra_selecao": SELECTION_RULE,
            "esperado": esperado,
        }
        _escrever_json(diagnostico_path, diagnostico)
        raise RuntimeError(
            "Checkpoint canônico Gate18G7F2 ausente. Materialize-o uma única vez com "
            "scripts/materializar_checkpoint_g7f2.py; o runtime não faz download de fontes históricas."
        )

    manifest = checkpoint.with_name(MANIFEST_FILENAME)
    if not manifest.exists():
        raise RuntimeError(f"Manifesto do checkpoint canônico ausente: {manifest}")
    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    sha = _sha256(checkpoint)
    if metadata.get("sha256_csv") != sha:
        raise RuntimeError(
            "SHA-256 do checkpoint canônico diverge do manifesto; arquivo pode ter sido alterado."
        )
    if metadata.get("checkpoint_id") != CHECKPOINT_ID:
        raise RuntimeError("Manifesto não identifica o checkpoint Gate18G7F2.")

    frame = pd.read_csv(checkpoint, dtype={"codigo_setor": "string"})
    canonico = _validar_frame(frame, esperado)
    counts = _macro_counts(canonico)
    manifesto_counts = {
        int(key): int(value) for key, value in metadata.get("macro_composicao", {}).items()
    }
    if int(metadata.get("n_setores", -1)) != len(canonico) or manifesto_counts != counts:
        raise RuntimeError("Cardinalidade ou composição do manifesto diverge do CSV canônico.")

    diagnostico = {
        "status": "ok",
        "checkpoint_id": CHECKPOINT_ID,
        "fonte_checkpoint": str(checkpoint),
        "papel": "checkpoint_canonico_local_imutavel",
        "sha256": sha,
        "regra_selecao": metadata.get("regra_selecao", SELECTION_RULE),
        "n_setores": len(canonico),
        "macro_composicao": counts,
        "download_runtime": False,
    }
    _escrever_json(diagnostico_path, diagnostico)
    return canonico, diagnostico


def _resolver_coluna(colunas: list[object], aliases: tuple[str, ...]) -> object | None:
    normalizadas = {_normalizar_nome(coluna): coluna for coluna in colunas}
    return next((normalizadas[alias] for alias in aliases if alias in normalizadas), None)


def _extrair_semantica(frame: pd.DataFrame, esperado: int) -> pd.DataFrame:
    colunas = list(frame.columns)
    setor = _resolver_coluna(colunas, SECTOR_ALIASES)
    macro = _resolver_coluna(colunas, MACRO_ALIASES)
    isau = _resolver_coluna(colunas, ISAU_ALIASES)
    if setor is None or macro is None or isau is None:
        raise RuntimeError("Fonte não contém as colunas semânticas de setor, macrotipo e ISAU-C3.")

    trabalho = frame[[setor, macro, isau]].copy()
    trabalho["codigo_setor"] = trabalho[setor].map(_normalizar_codigo)
    trabalho["macrotipo_checkpoint"] = pd.to_numeric(trabalho[macro], errors="coerce")
    selecao = trabalho["macrotipo_checkpoint"].isin([2, 3, 4]) & trabalho[isau].notna()
    canonico = trabalho.loc[selecao, ["codigo_setor", "macrotipo_checkpoint"]]
    return _validar_frame(canonico, esperado)


def _ler_excel_semantico(path: Path, sheet: str | None) -> tuple[pd.DataFrame, str]:
    workbook = pd.ExcelFile(path)
    sheets = [sheet] if sheet else workbook.sheet_names
    for nome in sheets:
        if nome not in workbook.sheet_names:
            continue
        preview = pd.read_excel(path, sheet_name=nome, header=None, nrows=80)
        for indice, row in preview.iterrows():
            nomes = {_normalizar_nome(valor) for valor in row.tolist() if pd.notna(valor)}
            tem_setor = any(alias in nomes for alias in SECTOR_ALIASES)
            tem_macro = any(alias in nomes for alias in MACRO_ALIASES)
            tem_isau = any(alias in nomes for alias in ISAU_ALIASES)
            if tem_setor and tem_macro and tem_isau:
                return pd.read_excel(path, sheet_name=nome, header=int(indice)), nome
    raise RuntimeError("Nenhuma aba XLSX contém cabeçalho semântico setor/macrotipo/ISAU-C3.")


def materializar_checkpoint_de_fonte(
    fonte: str | Path,
    destino: str | Path,
    *,
    sheet: str | None = None,
    esperado: int = EXPECTED_INTEGRATED,
) -> tuple[Path, Path]:
    """Materializa o Gate18G7F2 a partir de fonte histórica local auditável."""
    path = Path(fonte)
    if not path.exists():
        raise FileNotFoundError(path)
    suffix = path.suffix.lower()
    origem = path.name
    if suffix in {".xlsx", ".xlsm"}:
        frame, aba = _ler_excel_semantico(path, sheet)
        origem = f"{path.name}::{aba}"
    elif suffix == ".csv":
        frame = pd.read_csv(path, low_memory=False)
    elif suffix == ".parquet":
        frame = pd.read_parquet(path)
    elif suffix == ".gpkg":
        import geopandas as gpd

        frame = pd.DataFrame(gpd.read_file(path))
    else:
        raise RuntimeError(f"Formato de fonte não suportado para materialização: {suffix}")

    canonico = _extrair_semantica(frame, esperado)
    return escrever_checkpoint_canonico(canonico, destino, esperado=esperado, fonte=origem)
