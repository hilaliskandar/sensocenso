from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pandas as pd
import requests


G7E_SHEET_ID = "12B7bLrQgJh_pIyClDb24baiZGl8UKn4MQH8qWB7eL2Y"
G7E_EXPORT_URL = f"https://docs.google.com/spreadsheets/d/{G7E_SHEET_ID}/export?format=xlsx"
G7E_FILENAME = "TIC_TIM_GATE18G7E_VALIDACAO_ISAU_TIPOLOGIA_v3.xlsx"
G7E_DIAGNOSTICO_FILENAME = "TIC_TIM_GATE18G7E_diagnostico.json"
G7E_COMPOSICAO_MACRO_CANONICA = {2: 3568, 3: 3843, 4: 662}

_SETOR_ALIASES = ("CDSETOR", "CDSETOR2022", "CODIGOSETOR", "CODSETOR")
_MACRO_ALIASES = (
    "MACROFINAL",
    "MACROTIPOFINAL",
    "MACROG6",
    "MACROTIPO",
    "MACRO",
)
_ISAU_ALIASES = ("ISAUC3", "ISAUC3FINAL")


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


def _gravar_diagnostico(path: Path, payload: dict[str, object]) -> None:
    destino = path.parent / G7E_DIAGNOSTICO_FILENAME
    destino.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _detectar_linha_cabecalho(preview: pd.DataFrame) -> int | None:
    """Localiza o cabeçalho tabular sem presumir que esteja na primeira linha da aba."""
    candidatos: list[tuple[int, int]] = []
    setor_aliases = set(_SETOR_ALIASES)
    macro_aliases = set(_MACRO_ALIASES)
    isau_aliases = set(_ISAU_ALIASES)
    for idx, linha in preview.iterrows():
        nomes = {_normalizar_nome_coluna(v) for v in linha.tolist() if pd.notna(v)}
        if not (nomes & setor_aliases):
            continue
        score = 1
        if nomes & macro_aliases:
            score += 2
        if nomes & isau_aliases:
            score += 2
        candidatos.append((score, int(idx)))
    if not candidatos:
        return None
    return sorted(candidatos, key=lambda item: (-item[0], item[1]))[0][1]


def _ler_abas_checkpoint(path: Path) -> list[tuple[str, int, pd.DataFrame]]:
    """Lê apenas abas com cabeçalho setorial detectável, tolerando títulos/notas preambulares."""
    abas: list[tuple[str, int, pd.DataFrame]] = []
    with pd.ExcelFile(path) as xls:
        for aba in xls.sheet_names:
            preview = pd.read_excel(
                xls,
                sheet_name=aba,
                header=None,
                dtype=object,
                nrows=80,
            )
            linha_cabecalho = _detectar_linha_cabecalho(preview)
            if linha_cabecalho is None:
                continue
            df = pd.read_excel(
                xls,
                sheet_name=aba,
                header=linha_cabecalho,
                dtype=object,
            )
            abas.append((str(aba), linha_cabecalho, df))
    return abas


def _primeira_coluna(mapa: dict[str, object], aliases: tuple[str, ...]) -> object | None:
    return next((mapa[alias] for alias in aliases if alias in mapa), None)


def _candidato_semantico(df: pd.DataFrame) -> pd.DataFrame | None:
    mapa = {_normalizar_nome_coluna(c): c for c in df.columns}
    setor_col = _primeira_coluna(mapa, _SETOR_ALIASES)
    macro_col = _primeira_coluna(mapa, _MACRO_ALIASES)
    isau_col = _primeira_coluna(mapa, _ISAU_ALIASES)
    if setor_col is None:
        return None

    codigo = _normalizar_codigo_setor(df[setor_col])
    candidato = pd.DataFrame({"codigo_setor": codigo})
    if macro_col is not None:
        candidato["macrotipo_checkpoint"] = pd.to_numeric(df[macro_col], errors="coerce")
    if isau_col is not None:
        candidato["isau_c3_checkpoint"] = pd.to_numeric(df[isau_col], errors="coerce")
    return candidato


def _composicao_macrotipos(df: pd.DataFrame) -> dict[int, int] | None:
    if "macrotipo_checkpoint" not in df.columns:
        return None
    contagem = (
        pd.to_numeric(df["macrotipo_checkpoint"], errors="coerce")
        .dropna()
        .astype(int)
        .value_counts()
        .sort_index()
    )
    return {int(k): int(v) for k, v in contagem.items() if int(k) in (2, 3, 4)}


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
    workbook_meta: dict[str, object] = {
        "fonte": "Gate 18G7E — validação ISAU × tipologia final",
        "sheet_id": G7E_SHEET_ID,
        "url_exportacao": G7E_EXPORT_URL,
        "arquivo_cache": str(path),
        "tamanho_bytes": int(path.stat().st_size),
        "sha256": _sha256(path),
        "esperado_setores": int(esperado),
    }

    abas = _ler_abas_checkpoint(path)
    diagnostico: dict[str, dict[str, object]] = {}
    candidatos: list[tuple[int, str, str, pd.DataFrame, int]] = []
    for aba, linha_cabecalho, df in abas:
        cand = _candidato_semantico(df)
        colunas_brutas = [str(c) for c in df.columns]
        colunas_normalizadas = [_normalizar_nome_coluna(c) for c in df.columns]
        if cand is None:
            diagnostico[str(aba)] = {
                "linha_cabecalho_excel_1based": int(linha_cabecalho + 1),
                "colunas": colunas_brutas,
                "colunas_normalizadas": colunas_normalizadas,
                "erro": "sem coluna de setor reconhecida após releitura",
            }
            continue

        validos = cand.dropna(subset=["codigo_setor"]).copy()
        n_linhas_validas = int(len(validos))
        n_codigos = int(validos["codigo_setor"].nunique())
        n_duplicados = int(validos["codigo_setor"].duplicated(keep=False).sum())
        tem_macro = "macrotipo_checkpoint" in validos.columns
        tem_isau = "isau_c3_checkpoint" in validos.columns
        composicao = _composicao_macrotipos(validos)

        sem = validos.copy()
        regra: list[str] = []
        prioridade = 0
        n_apos_macro: int | None = None
        n_apos_isau: int | None = None
        if tem_macro:
            sem = sem.loc[sem["macrotipo_checkpoint"].isin([2, 3, 4])].copy()
            n_apos_macro = int(len(sem))
            regra.append("MACRO_FINAL in {2,3,4}")
            prioridade += 2
        if tem_isau:
            sem = sem.loc[sem["isau_c3_checkpoint"].notna()].copy()
            n_apos_isau = int(len(sem))
            regra.append("ISAU_C3 observado")
            prioridade += 2

        diagnostico[str(aba)] = {
            "linha_cabecalho_excel_1based": int(linha_cabecalho + 1),
            "colunas": colunas_brutas,
            "colunas_normalizadas": colunas_normalizadas,
            "linhas_setoriais_validas": n_linhas_validas,
            "codigos_validos_unicos": n_codigos,
            "linhas_com_codigo_duplicado": n_duplicados,
            "tem_macrotipo": tem_macro,
            "tem_isau_c3": tem_isau,
            "composicao_macrotipos_2_3_4": composicao,
            "n_apos_macro_234": n_apos_macro,
            "n_apos_isau_observado": n_apos_isau,
            "regra_semantica": " + ".join(regra),
            "n_resultante_regra": int(len(sem)),
        }

        if n_duplicados:
            continue
        if not (tem_macro or tem_isau):
            continue
        candidatos.append(
            (
                prioridade,
                str(aba),
                " + ".join(regra),
                sem,
                linha_cabecalho,
            )
        )

    payload_diag: dict[str, object] = {
        **workbook_meta,
        "abas_com_cabecalho_setorial": [aba for aba, _, _ in abas],
        "diagnostico_abas": diagnostico,
        "candidatos": [
            {"aba": aba, "regra": regra, "n": int(len(df))}
            for _, aba, regra, df, _ in candidatos
        ],
    }

    exatos = [c for c in candidatos if len(c[3]) == esperado]
    if esperado == 8073:
        exatos_com_composicao = [
            c
            for c in exatos
            if _composicao_macrotipos(c[3]) == G7E_COMPOSICAO_MACRO_CANONICA
        ]
        if exatos_com_composicao:
            exatos = exatos_com_composicao
        elif any("macrotipo_checkpoint" in c[3].columns for c in exatos):
            payload_diag["status"] = "falha_composicao_macrotipos"
            _gravar_diagnostico(path, payload_diag)
            raise AssertionError(
                "Checkpoint Gate 18G7E atingiu 8.073 setores, mas não reproduziu a composição "
                f"canônica dos macrotipos {G7E_COMPOSICAO_MACRO_CANONICA}; diagnostico={diagnostico}"
            )

    if not exatos:
        payload_diag["status"] = "falha_sem_candidato_exato"
        _gravar_diagnostico(path, payload_diag)
        resumo = [
            {"aba": aba, "regra": regra, "n": len(df)}
            for _, aba, regra, df, _ in candidatos
        ]
        raise AssertionError(
            "Checkpoint Gate 18G7E não reproduziu o universo integrado esperado por regra semântica; "
            f"esperado={esperado}; candidatos={resumo}; diagnostico={diagnostico}"
        )

    prioridade, aba, regra, escolhido, linha_cabecalho = sorted(
        exatos,
        key=lambda x: (-x[0], x[1]),
    )[0]
    del prioridade
    escolhido = escolhido.sort_values("codigo_setor").reset_index(drop=True)
    if escolhido["codigo_setor"].duplicated().any() or len(escolhido) != esperado:
        payload_diag["status"] = "falha_integridade_candidato"
        _gravar_diagnostico(path, payload_diag)
        raise AssertionError("Checkpoint integrado possui duplicidades ou cardinalidade inválida.")

    meta: dict[str, object] = {
        **workbook_meta,
        "aba_selecionada": aba,
        "linha_cabecalho_excel_1based": int(linha_cabecalho + 1),
        "regra_selecao": regra,
        "n_setores": int(len(escolhido)),
        "composicao_macrotipos_2_3_4": _composicao_macrotipos(escolhido),
        "diagnostico_abas": diagnostico,
    }
    payload_diag.update(
        {
            "status": "ok",
            "aba_selecionada": aba,
            "linha_cabecalho_excel_1based": int(linha_cabecalho + 1),
            "regra_selecao": regra,
            "n_setores": int(len(escolhido)),
            "composicao_macrotipos_2_3_4": _composicao_macrotipos(escolhido),
        }
    )
    _gravar_diagnostico(path, payload_diag)
    return escolhido, meta
