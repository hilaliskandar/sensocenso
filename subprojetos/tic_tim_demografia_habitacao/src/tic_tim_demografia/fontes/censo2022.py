from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Iterable

import pandas as pd


COLUNAS_DEMOGRAFIA = ["V01006"] + [f"V010{i:02d}" for i in range(31, 42)]


def _localizar_csv_no_zip(path: Path, token: str) -> str:
    with zipfile.ZipFile(path) as zf:
        candidatos = [
            n for n in zf.namelist()
            if n.lower().endswith(".csv") and token.casefold() in n.casefold()
        ]
    if len(candidatos) != 1:
        raise ValueError(
            f"ZIP deve conter exatamente um CSV compatível com '{token}'; candidatos={candidatos}"
        )
    return candidatos[0]


def localizar_csv_demografia_no_zip(path: Path) -> str:
    return _localizar_csv_no_zip(path, "demografia")


def localizar_csv_basico_no_zip(path: Path) -> str:
    return _localizar_csv_no_zip(path, "basico")


def _detectar_encoding(bruto: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin1"):
        try:
            bruto.decode(encoding, errors="strict")
            return encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("utf-8", bruto, 0, 1, "codificação CSV não reconhecida")


def _detectar_separador(amostra: bytes, *, encoding: str) -> str:
    texto = amostra.decode(encoding, errors="strict")
    primeira = texto.splitlines()[0] if texto.splitlines() else ""
    contagens = {";": primeira.count(";"), ",": primeira.count(","), "\t": primeira.count("\t")}
    separador, n = max(contagens.items(), key=lambda x: x[1])
    if n == 0:
        raise ValueError("Não foi possível detectar separador do CSV do Censo 2022.")
    return separador


def _ler_membro_csv(path: Path, membro: str) -> pd.DataFrame:
    with zipfile.ZipFile(path) as zf:
        with zf.open(membro) as f:
            bruto = f.read()
    encoding = _detectar_encoding(bruto)
    sep = _detectar_separador(bruto[:65536], encoding=encoding)
    return pd.read_csv(io.BytesIO(bruto), sep=sep, dtype="string", encoding=encoding)


def ler_setores_urbanos_basico_zip(path: Path, *, codigos_municipais: Iterable[str]) -> pd.DataFrame:
    codigos = {str(c) for c in codigos_municipais}
    df = _ler_membro_csv(path, localizar_csv_basico_no_zip(path))
    mapa = {str(c).strip().casefold(): str(c) for c in df.columns}
    coluna_setor = mapa.get("cd_setor")
    coluna_situacao = mapa.get("situacao")
    if coluna_setor is None or coluna_situacao is None:
        raise ValueError("Arquivo Básico 2022 sem CD_SETOR e/ou SITUACAO.")

    work = df[[coluna_setor, coluna_situacao]].copy()
    work["codigo_ibge"] = work[coluna_setor].astype("string").str.slice(0, 7)
    work["situacao_norm"] = work[coluna_situacao].astype("string").str.strip().str.casefold()
    work = work.loc[work["codigo_ibge"].isin(codigos)]
    observadas = sorted(work["situacao_norm"].dropna().unique().tolist())
    inesperadas = [x for x in observadas if x not in {"urbana", "rural"}]
    if inesperadas:
        raise ValueError(f"Categorias SITUACAO inesperadas no Básico 2022: {inesperadas}")

    urbanos = work.loc[work["situacao_norm"].eq("urbana"), [coluna_setor, "codigo_ibge"]].copy()
    if urbanos.empty:
        raise ValueError("Nenhum setor urbano encontrado para os municípios configurados.")
    if urbanos[coluna_setor].duplicated().any():
        raise ValueError("CD_SETOR duplicado no arquivo Básico 2022.")
    return urbanos.rename(columns={coluna_setor: "codigo_setor"}).reset_index(drop=True)


def ler_demografia_setorial_zip(
    path: Path,
    *,
    codigos_municipais: Iterable[str],
    setores_permitidos: Iterable[str] | None = None,
) -> pd.DataFrame:
    codigos = {str(c) for c in codigos_municipais}
    df = _ler_membro_csv(path, localizar_csv_demografia_no_zip(path))

    coluna_setor = next((c for c in df.columns if str(c).strip().casefold() == "cd_setor"), None)
    if coluna_setor is None:
        raise ValueError(f"Coluna CD_SETOR ausente no arquivo demografia 2022: {list(df.columns)[:20]}")
    faltantes = [c for c in COLUNAS_DEMOGRAFIA if c not in df.columns]
    if faltantes:
        raise ValueError(f"Variáveis demográficas 2022 obrigatórias ausentes: {faltantes}")

    df["codigo_ibge"] = df[coluna_setor].astype("string").str.slice(0, 7)
    mask = df["codigo_ibge"].isin(codigos)
    if setores_permitidos is not None:
        permitidos = {str(x) for x in setores_permitidos}
        mask &= df[coluna_setor].astype("string").isin(permitidos)
    recorte = df.loc[mask, [coluna_setor, "codigo_ibge"] + COLUNAS_DEMOGRAFIA].copy()
    if recorte.empty:
        raise ValueError("Nenhum setor do universo configurado foi encontrado no arquivo 2022.")
    if recorte[coluna_setor].duplicated().any():
        raise ValueError("CD_SETOR duplicado no arquivo demografia 2022.")
    return recorte.rename(columns={coluna_setor: "codigo_setor"})


def diagnosticar_simbolos_demografia(setores: pd.DataFrame) -> dict:
    """Documenta células não numéricas sem tentar reconstruir dados protegidos.

    Nos Agregados por Setores Censitários 2022, ``x``/``X`` sinaliza omissão por
    tratamento de sigilo. O diagnóstico identifica incidência, variável e
    município, mas deliberadamente não infere valores suprimidos por diferença.
    """
    por_variavel: dict[str, dict] = {}
    setores_afetados: set[str] = set()
    municipios_afetados: set[str] = set()
    for coluna in COLUNAS_DEMOGRAFIA:
        bruto = setores[coluna].astype("string").str.strip()
        numeric = pd.to_numeric(bruto, errors="coerce")
        mask = numeric.isna() & bruto.notna()
        if not mask.any():
            continue
        simbolos = bruto.loc[mask].value_counts(dropna=False).to_dict()
        subset = setores.loc[mask, ["codigo_setor", "codigo_ibge"]].copy()
        setores_afetados.update(subset["codigo_setor"].astype(str))
        municipios_afetados.update(subset["codigo_ibge"].astype(str))
        por_variavel[coluna] = {
            "celulas": int(mask.sum()),
            "simbolos": {str(k): int(v) for k, v in simbolos.items()},
            "municipios": sorted(subset["codigo_ibge"].astype(str).unique().tolist()),
            "amostra_setores": sorted(subset["codigo_setor"].astype(str).unique().tolist())[:25],
        }
    return {
        "setores_analisados": int(len(setores)),
        "setores_com_algum_simbolo": int(len(setores_afetados)),
        "municipios_com_algum_simbolo": sorted(municipios_afetados),
        "n_municipios_com_algum_simbolo": int(len(municipios_afetados)),
        "por_variavel": por_variavel,
        "regra": (
            "x/X é tratado como dado omitido por sigilo; não converter em zero e não inferir "
            "valor individual por diferença"
        ),
    }


def agregar_demografia_2022_municipio(setores: pd.DataFrame) -> pd.DataFrame:
    work = setores.copy()
    for coluna in COLUNAS_DEMOGRAFIA:
        bruto = work[coluna].astype("string").str.strip()
        num = pd.to_numeric(bruto, errors="coerce")
        invalidos = sorted(bruto[num.isna() & bruto.notna()].dropna().unique().tolist())
        if invalidos:
            raise ValueError(
                f"Valores não numéricos em {coluna}; dados protegidos/ausentes não serão convertidos em zero: {invalidos}"
            )
        work[coluna] = num

    colunas_soma = COLUNAS_DEMOGRAFIA
    faltas_setoriais = work.groupby("codigo_ibge")[colunas_soma].apply(lambda x: x.isna().any().any())
    ruins = faltas_setoriais[faltas_setoriais].index.astype(str).tolist()
    if ruins:
        raise ValueError(
            "Há valores ausentes nas variáveis necessárias em setores dos municípios: " + ", ".join(ruins)
        )

    por_municipio = work.groupby("codigo_ibge", as_index=False)[colunas_soma].sum(min_count=1)
    por_municipio["ano"] = 2022
    por_municipio["pop_0_14"] = por_municipio[["V01031", "V01032", "V01033"]].sum(axis=1)
    por_municipio["pop_15_59"] = por_municipio[
        ["V01034", "V01035", "V01036", "V01037", "V01038", "V01039"]
    ].sum(axis=1)
    por_municipio["pop_60_mais"] = por_municipio[["V01040", "V01041"]].sum(axis=1)
    por_municipio["pop_total_harmonizada"] = (
        por_municipio["pop_0_14"] + por_municipio["pop_15_59"] + por_municipio["pop_60_mais"]
    )
    por_municipio["pop_total_fonte"] = por_municipio["V01006"]
    por_municipio["diferenca_fechamento"] = (
        por_municipio["pop_total_harmonizada"] - por_municipio["pop_total_fonte"]
    )
    if not por_municipio["diferenca_fechamento"].eq(0).all():
        ruins = por_municipio.loc[
            por_municipio["diferenca_fechamento"].ne(0),
            ["codigo_ibge", "pop_total_harmonizada", "pop_total_fonte", "diferenca_fechamento"],
        ]
        raise AssertionError(
            "As bandas etárias 2022 não fecham com V01006:\n" + ruins.to_string(index=False)
        )

    saida = por_municipio[
        [
            "codigo_ibge",
            "ano",
            "pop_0_14",
            "pop_15_59",
            "pop_60_mais",
            "pop_total_harmonizada",
            "pop_total_fonte",
            "diferenca_fechamento",
        ]
    ].copy()
    inteiras = ["pop_0_14", "pop_15_59", "pop_60_mais", "pop_total_harmonizada", "pop_total_fonte", "diferenca_fechamento"]
    saida[inteiras] = saida[inteiras].astype("int64")
    return saida.sort_values("codigo_ibge").reset_index(drop=True)
