from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pandas as pd
import requests


G7E_SHEET_ID = "12B7bLrQgJh_pIyClDb24baiZGl8UKn4MQH8qWB7eL2Y"
G7E_EXPORT_URL = f"https://docs.google.com/spreadsheets/d/{G7E_SHEET_ID}/export?format=xlsx"
G7E_FILENAME = "TIC_TIM_GATE18G7E_VALIDACAO_ISAU_TIPOLOGIA_v3.xlsx"


def _normalizar_nome_coluna(valor: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(valor).upper())


def _normalizar_codigo_setor(serie: pd.Series) -> pd.Series:
    out = serie.astype("string").str.strip().str.replace(r"\.0$", "", regex=True)
    return out.where(out.str.fullmatch(r"\d{15}", na=False))


def _baixar_checkpoint(destino: Path) -> None:
    if destino.exists() and destino.stat().st_size > 0:
        return
    destino.parent.mkdir(parents=True, exist_ok=True)
    resposta = requests.get(G7E_EXPORT_URL, timeout=180)
    resposta.raise_for_status()
    if len(resposta.content) < 10_000:
        raise ValueError(
            "Exportação do checkpoint Gate 18G7E retornou conteúdo inesperadamente pequeno: "
            f"{len(resposta.content)} bytes"
        )
    destino.write_bytes(resposta.content)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


def _candidato_semantico(df: pd.DataFrame) -> pd.DataFrame | None:
    mapa = {_normalizar_nome_coluna(c): c for c in df.columns}
    setor_col = next((mapa[c] for c in ("CDSETOR", "CODIGOSETOR", "CODSETOR") if c in mapa), None)
    macro_col = next((mapa[c] for c in ("MACROFINAL", "MACROTIPO", "MACROTIPOFINAL") if c in mapa), None)
    isau_col = next((mapa[c] for c in ("ISAUC3", "ISAUC3FINAL") if c in mapa), None)
    if setor_col is None:
        return None

    codigo = _normalizar_codigo_setor(df[setor_col])
    candidato = pd.DataFrame({"codigo_setor": codigo})
    if macro_col is not None:
        candidato["macrotipo_checkpoint"] = pd.to_numeric(df[macro_col], errors="coerce")
    if isau_col is not None:
        candidato["isau_c3_checkpoint"] = pd.to_numeric(df[isau_col], errors="coerce")
    return candidato


def carregar_universo_integrado_canonico(
    raw_root: Path,
    *,
    esperado: int = 8073,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Carrega o checkpoint canônico Gate 18G7E sem reconstruir tipologia por inferência.

    O fechamento histórico define o universo integrado como a interseção entre a
    tipologia estrutural final e o ISAU-C3. O workbook G7E é tratado como checkpoint
    upstream explícito; ele não é usado para recalibrar os indicadores desta pipeline.
    """
    path = raw_root / "checkpoints" / G7E_FILENAME
    _baixar_checkpoint(path)
    abas = pd.read_excel(path, sheet_name=None, dtype=object)

    diagnostico: dict[str, dict[str, int | bool]] = {}
    candidatos: list[tuple[int, str, str, pd.DataFrame]] = []
    for aba, df in abas.items():
        cand = _candidato_semantico(df)
        if cand is None:
            continue
        validos = cand.dropna(subset=["codigo_setor"]).copy()
        n_codigos = int(validos["codigo_setor"].nunique())
        tem_macro = "macrotipo_checkpoint" in validos.columns
        tem_isau = "isau_c3_checkpoint" in validos.columns
        diagnostico[str(aba)] = {
            "codigos_validos_unicos": n_codigos,
            "tem_macrotipo": tem_macro,
            "tem_isau_c3": tem_isau,
        }

        if tem_macro and tem_isau:
            sem = validos.loc[
                validos["macrotipo_checkpoint"].isin([2, 3, 4])
                & validos["isau_c3_checkpoint"].notna()
            ].copy()
            sem = sem.drop_duplicates("codigo_setor")
            candidatos.append((2, str(aba), "MACRO_FINAL in {2,3,4} + ISAU_C3 observado", sem))

        direto = validos.drop_duplicates("codigo_setor")
        candidatos.append((1, str(aba), "todos os códigos setoriais válidos da aba", direto))

    exatos = [c for c in candidatos if len(c[3]) == esperado]
    if not exatos:
        resumo = [
            {"aba": aba, "regra": regra, "n": len(df)}
            for _, aba, regra, df in candidatos
        ]
        raise AssertionError(
            "Checkpoint Gate 18G7E não reproduziu o universo integrado esperado; "
            f"esperado={esperado}; candidatos={resumo}; diagnostico={diagnostico}"
        )

    prioridade, aba, regra, escolhido = sorted(exatos, key=lambda x: (-x[0], x[1]))[0]
    del prioridade
    escolhido = escolhido.drop_duplicates("codigo_setor").sort_values("codigo_setor").reset_index(drop=True)
    if escolhido["codigo_setor"].duplicated().any() or len(escolhido) != esperado:
        raise AssertionError("Checkpoint integrado possui duplicidades ou cardinalidade inválida.")

    meta: dict[str, object] = {
        "fonte": "Gate 18G7E — validação ISAU × tipologia final",
        "sheet_id": G7E_SHEET_ID,
        "url_exportacao": G7E_EXPORT_URL,
        "arquivo_cache": str(path),
        "sha256": _sha256(path),
        "aba_selecionada": aba,
        "regra_selecao": regra,
        "n_setores": int(len(escolhido)),
        "diagnostico_abas": diagnostico,
    }
    return escolhido, meta
