from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Iterator

import pandas as pd
import requests


G7E_SHEET_ID = "12B7bLrQgJh_pIyClDb24baiZGl8UKn4MQH8qWB7eL2Y"
G7E_EXPORT_URL = f"https://docs.google.com/spreadsheets/d/{G7E_SHEET_ID}/export?format=xlsx"
G7E_FILENAME = "TIC_TIM_GATE18G7E_VALIDACAO_ISAU_TIPOLOGIA_v3.xlsx"
G7E_DIAGNOSTICO_FILENAME = "TIC_TIM_GATE18G7E_diagnostico.json"
G7E_DOWNLOAD_DIAGNOSTICO_FILENAME = "TIC_TIM_GATE18G7E_download.json"

# Gate 18G11 v1.1 e posterior ao G7E, publico e reprodutivel. A aba
# 02_BASE_SETORIAL_ESCORES preserva CD_SETOR, MACRO_FINAL e ISAU_C3 e pode
# funcionar como espelho auditavel da mesma regra estrutural do G7E.
G11_SHEET_ID = "1kuVOXyt5PsM6KqVZFU8SxxwRlOClna65V_kn1A7zCzE"
G11_EXPORT_URL = f"https://docs.google.com/spreadsheets/d/{G11_SHEET_ID}/export?format=xlsx"
G11_FILENAME = "TIC_TIM_GATE18G11_GATES_EXTERNOS_BP_v1.1_PUBLICA.xlsx"
G11_DOWNLOAD_DIAGNOSTICO_FILENAME = "TIC_TIM_GATE18G11_publica_download.json"

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


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


def _gravar_json(destino: Path, payload: dict[str, object]) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _validar_xlsx(path: Path, *, tamanho_minimo: int = 1) -> None:
    tamanho = int(path.stat().st_size)
    if tamanho < tamanho_minimo:
        raise ValueError(f"Workbook XLSX inesperadamente pequeno: {tamanho} bytes")
    if not zipfile.is_zipfile(path):
        raise ValueError("Arquivo recebido nao e um XLSX/ZIP valido.")


def _prefixo_textual_resposta(resposta: requests.Response, limite: int = 500) -> str | None:
    content_type = str(resposta.headers.get("Content-Type", "")).lower()
    if not any(token in content_type for token in ("text/", "json", "html", "xml")):
        return None
    try:
        texto = resposta.text[:limite]
    except Exception:  # pragma: no cover
        return None
    return re.sub(r"\s+", " ", texto).strip()


def _baixar_xlsx(
    *,
    url: str,
    destino: Path,
    diagnostico_path: Path,
    rotulo: str,
) -> dict[str, object]:
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(destino.suffix + ".part")
    meta: dict[str, object] = {
        "status": "iniciando",
        "fonte": rotulo,
        "url_solicitada": url,
        "arquivo_destino": str(destino),
    }
    _gravar_json(diagnostico_path, meta)
    try:
        resposta = requests.get(url, timeout=180, allow_redirects=True)
        meta.update(
            {
                "http_status": int(resposta.status_code),
                "url_final": str(resposta.url),
                "content_type": str(resposta.headers.get("Content-Type", "")),
                "content_length_header": str(resposta.headers.get("Content-Length", "")),
                "tamanho_resposta_bytes": int(len(resposta.content)),
            }
        )
        prefixo = _prefixo_textual_resposta(resposta)
        if prefixo:
            meta["prefixo_resposta_textual"] = prefixo
        _gravar_json(diagnostico_path, meta)
        resposta.raise_for_status()
        temporario.write_bytes(resposta.content)
        _validar_xlsx(temporario, tamanho_minimo=10_000)
        temporario.replace(destino)
        meta.update(
            {
                "status": "ok",
                "tamanho_arquivo_bytes": int(destino.stat().st_size),
                "sha256": _sha256(destino),
            }
        )
        _gravar_json(diagnostico_path, meta)
        return meta
    except Exception as exc:
        if temporario.exists():
            meta["tamanho_temporario_bytes"] = int(temporario.stat().st_size)
            temporario.unlink()
        meta.update(
            {
                "status": "erro",
                "erro_tipo": type(exc).__name__,
                "erro": str(exc),
            }
        )
        _gravar_json(diagnostico_path, meta)
        raise


def _fontes_checkpoint(raw_root: Path) -> Iterator[tuple[Path, dict[str, object]]]:
    pasta = raw_root / "checkpoints"
    pasta.mkdir(parents=True, exist_ok=True)
    fontes = [
        {
            "rotulo": "Gate 18G7E — validacao ISAU x tipologia final",
            "sheet_id": G7E_SHEET_ID,
            "url": G7E_EXPORT_URL,
            "filename": G7E_FILENAME,
            "diag": G7E_DOWNLOAD_DIAGNOSTICO_FILENAME,
            "papel": "checkpoint_canonico_primario",
        },
        {
            "rotulo": "Gate 18G11 v1.1 publica — espelho setorial posterior do G7E",
            "sheet_id": G11_SHEET_ID,
            "url": G11_EXPORT_URL,
            "filename": G11_FILENAME,
            "diag": G11_DOWNLOAD_DIAGNOSTICO_FILENAME,
            "papel": "fallback_publico_auditavel",
        },
    ]

    # Primeiro usa caches validos. Isso mantem os testes offline e evita rede desnecessaria.
    for fonte in fontes:
        path = pasta / str(fonte["filename"])
        if not path.exists() or path.stat().st_size <= 0:
            continue
        try:
            _validar_xlsx(path)
        except Exception:
            path.unlink()
            continue
        yield path, {
            **fonte,
            "origem_acesso": "cache_local",
            "tamanho_bytes": int(path.stat().st_size),
            "sha256": _sha256(path),
        }

    # Sem cache util, tenta a fonte primaria e depois o espelho publico.
    for fonte in fontes:
        path = pasta / str(fonte["filename"])
        if path.exists() and path.stat().st_size > 0:
            continue
        try:
            download_meta = _baixar_xlsx(
                url=str(fonte["url"]),
                destino=path,
                diagnostico_path=pasta / str(fonte["diag"]),
                rotulo=str(fonte["rotulo"]),
            )
        except Exception:
            continue
        yield path, {
            **fonte,
            "origem_acesso": "download",
            "tamanho_bytes": int(path.stat().st_size),
            "sha256": _sha256(path),
            "download": download_meta,
        }


def _detectar_linha_cabecalho(preview: pd.DataFrame) -> int | None:
    candidatos: list[tuple[int, int]] = []
    setor_aliases = set(_SETOR_ALIASES)
    macro_aliases = set(_MACRO_ALIASES)
    isau_aliases = set(_ISAU_ALIASES)
    for idx, linha in preview.iterrows():
        nomes = {_normalizar_nome_coluna(v) for v in linha.tolist() if pd.notna(v)}
        if not (nomes & setor_aliases):
            continue
        score = 1 + 2 * bool(nomes & macro_aliases) + 2 * bool(nomes & isau_aliases)
        candidatos.append((score, int(idx)))
    if not candidatos:
        return None
    return sorted(candidatos, key=lambda item: (-item[0], item[1]))[0][1]


def _ler_abas_checkpoint(path: Path) -> list[tuple[str, int, pd.DataFrame]]:
    abas: list[tuple[str, int, pd.DataFrame]] = []
    with pd.ExcelFile(path) as xls:
        for aba in xls.sheet_names:
            preview = pd.read_excel(xls, sheet_name=aba, header=None, dtype=object, nrows=80)
            linha_cabecalho = _detectar_linha_cabecalho(preview)
            if linha_cabecalho is None:
                continue
            df = pd.read_excel(xls, sheet_name=aba, header=linha_cabecalho, dtype=object)
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


def _extrair_universo(
    path: Path,
    *,
    esperado: int,
) -> tuple[pd.DataFrame, dict[str, object]]:
    diagnostico: dict[str, dict[str, object]] = {}
    candidatos: list[tuple[int, str, pd.DataFrame]] = []
    for aba, linha_cabecalho, df in _ler_abas_checkpoint(path):
        cand = _candidato_semantico(df)
        if cand is None:
            continue
        validos = cand.dropna(subset=["codigo_setor"]).copy()
        tem_macro = "macrotipo_checkpoint" in validos.columns
        tem_isau = "isau_c3_checkpoint" in validos.columns
        sem = validos.copy()
        if tem_macro:
            sem = sem.loc[sem["macrotipo_checkpoint"].isin([2, 3, 4])].copy()
        if tem_isau:
            sem = sem.loc[sem["isau_c3_checkpoint"].notna()].copy()
        duplicados = int(validos["codigo_setor"].duplicated(keep=False).sum())
        diagnostico[aba] = {
            "linha_cabecalho_excel_1based": int(linha_cabecalho + 1),
            "linhas_setoriais_validas": int(len(validos)),
            "codigos_validos_unicos": int(validos["codigo_setor"].nunique()),
            "linhas_com_codigo_duplicado": duplicados,
            "tem_macrotipo": tem_macro,
            "tem_isau_c3": tem_isau,
            "n_resultante_macro_234_e_isau_observado": int(len(sem)) if tem_macro and tem_isau else None,
            "composicao_resultante": _composicao_macrotipos(sem) if tem_macro else None,
        }
        # O Gate 18G7E exige explicitamente as duas dimensoes; nao aceitamos um
        # conjunto de 8.073 obtido apenas por cardinalidade de uma delas.
        if duplicados or not (tem_macro and tem_isau):
            continue
        candidatos.append((linha_cabecalho, aba, sem))

    exatos = [c for c in candidatos if len(c[2]) == esperado]
    if esperado == 8073:
        exatos = [c for c in exatos if _composicao_macrotipos(c[2]) == G7E_COMPOSICAO_MACRO_CANONICA]
    if not exatos:
        raise AssertionError(
            "Workbook nao reproduziu o Gate 18G7E por regra semantica estrita; "
            f"esperado={esperado}; diagnostico={diagnostico}"
        )

    linha_cabecalho, aba, escolhido = sorted(exatos, key=lambda x: x[1])[0]
    escolhido = escolhido.sort_values("codigo_setor").reset_index(drop=True)
    if escolhido["codigo_setor"].duplicated().any() or len(escolhido) != esperado:
        raise AssertionError("Checkpoint integrado possui duplicidades ou cardinalidade invalida.")
    return escolhido, {
        "aba_selecionada": aba,
        "linha_cabecalho_excel_1based": int(linha_cabecalho + 1),
        "regra_selecao": "MACRO_FINAL in {2,3,4} + ISAU_C3 observado",
        "n_setores": int(len(escolhido)),
        "composicao_macrotipos_2_3_4": _composicao_macrotipos(escolhido),
        "diagnostico_abas": diagnostico,
    }


def carregar_universo_integrado_canonico(
    raw_root: Path,
    *,
    esperado: int = 8073,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Carrega o universo integrado canonico sem reconstruir tipologia por inferencia.

    Prioriza o workbook historico G7E. Se ele estiver inacessivel ao runner, usa o
    Gate 18G11 v1.1 publico somente como espelho posterior, exigindo a mesma regra
    estrutural, a mesma cardinalidade e a composicao canonica dos macrotipos.
    """
    erros: list[dict[str, object]] = []
    diag_path = raw_root / "checkpoints" / G7E_DIAGNOSTICO_FILENAME
    encontrou_fonte = False
    for path, fonte_meta in _fontes_checkpoint(raw_root):
        encontrou_fonte = True
        try:
            universo, extracao_meta = _extrair_universo(path, esperado=esperado)
        except Exception as exc:
            erros.append(
                {
                    "fonte": fonte_meta.get("rotulo"),
                    "arquivo": str(path),
                    "erro_tipo": type(exc).__name__,
                    "erro": str(exc),
                }
            )
            continue

        meta: dict[str, object] = {
            "fonte": fonte_meta["rotulo"],
            "papel_fonte": fonte_meta["papel"],
            "sheet_id": fonte_meta["sheet_id"],
            "url_exportacao": fonte_meta["url"],
            "arquivo_cache": str(path),
            "tamanho_bytes": int(path.stat().st_size),
            "sha256": _sha256(path),
            "esperado_setores": int(esperado),
            **extracao_meta,
            "tentativas_anteriores_falhas": erros,
        }
        _gravar_json(diag_path, {"status": "ok", **meta})
        return universo, meta

    payload = {
        "status": "falha",
        "esperado_setores": int(esperado),
        "fontes_encontradas": encontrou_fonte,
        "tentativas": erros,
        "nota": (
            "G7E e a fonte primaria. G11 v1.1 publica so e aceitavel se reproduzir "
            "8.073 setores e a composicao canonica 3.568/3.843/662 pela mesma regra."
        ),
    }
    _gravar_json(diag_path, payload)
    raise RuntimeError(
        "Nao foi possivel obter um checkpoint auditavel que reproduza o Gate 18G7E; "
        f"tentativas={erros}"
    )
