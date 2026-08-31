from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Iterable

import pandas as pd


COLUNAS_DEMOGRAFIA = ["V01006"] + [f"V010{i:02d}" for i in range(31, 42)]


def localizar_csv_demografia_no_zip(path: Path) -> str:
    with zipfile.ZipFile(path) as zf:
        candidatos = [
            n for n in zf.namelist()
            if n.lower().endswith(".csv") and "demografia" in n.lower()
        ]
    if len(candidatos) != 1:
        raise ValueError(
            f"ZIP demografia 2022 deve conter exatamente um CSV de demografia; candidatos={candidatos}"
        )
    return candidatos[0]


def _detectar_separador(amostra: bytes) -> str:
    texto = amostra.decode("utf-8-sig", errors="replace")
    primeira = texto.splitlines()[0] if texto.splitlines() else ""
    contagens = {";": primeira.count(";"), ",": primeira.count(","), "\t": primeira.count("\t")}
    separador, n = max(contagens.items(), key=lambda x: x[1])
    if n == 0:
        raise ValueError("Não foi possível detectar separador do CSV demografia 2022.")
    return separador


def ler_demografia_setorial_zip(path: Path, *, codigos_municipais: Iterable[str]) -> pd.DataFrame:
    """Lê somente os setores pertencentes ao universo configurado.

    O código municipal é obtido dos sete primeiros dígitos de CD_SETOR. Valores
    especiais permanecem ausentes: a rotina não os converte em zero.
    """
    codigos = {str(c) for c in codigos_municipais}
    membro = localizar_csv_demografia_no_zip(path)
    with zipfile.ZipFile(path) as zf:
        with zf.open(membro) as f:
            bruto = f.read()
    sep = _detectar_separador(bruto[:65536])
    df = pd.read_csv(io.BytesIO(bruto), sep=sep, dtype="string", encoding="utf-8-sig")

    coluna_setor = next((c for c in df.columns if str(c).strip().casefold() == "cd_setor"), None)
    if coluna_setor is None:
        raise ValueError(f"Coluna CD_SETOR ausente no arquivo demografia 2022: {list(df.columns)[:20]}")
    faltantes = [c for c in COLUNAS_DEMOGRAFIA if c not in df.columns]
    if faltantes:
        raise ValueError(f"Variáveis demográficas 2022 obrigatórias ausentes: {faltantes}")

    df["codigo_ibge"] = df[coluna_setor].astype("string").str.slice(0, 7)
    recorte = df.loc[df["codigo_ibge"].isin(codigos), [coluna_setor, "codigo_ibge"] + COLUNAS_DEMOGRAFIA].copy()
    if recorte.empty:
        raise ValueError("Nenhum setor dos municípios configurados foi encontrado no arquivo 2022.")
    return recorte.rename(columns={coluna_setor: "codigo_setor"})


def agregar_demografia_2022_municipio(setores: pd.DataFrame) -> pd.DataFrame:
    """Agrega setores para as bandas canônicas da série longitudinal.

    Segundo o dicionário oficial do Censo 2022, V01031–V01041 são as faixas
    etárias de ambos os sexos: 0–4, 5–9, 10–14, 15–19, 20–24, 25–29,
    30–39, 40–49, 50–59, 60–69 e 70+; V01006 é a quantidade de moradores.
    """
    work = setores.copy()
    for coluna in COLUNAS_DEMOGRAFIA:
        bruto = work[coluna].astype("string").str.strip()
        num = pd.to_numeric(bruto, errors="coerce")
        invalidos = sorted(bruto[num.isna() & bruto.notna()].dropna().unique().tolist())
        if invalidos:
            raise ValueError(
                f"Valores não numéricos em {coluna}; ausência/supressão não será convertida em zero: {invalidos}"
            )
        work[coluna] = num

    # Se um setor possuir ausência em qualquer componente necessário, o município
    # não pode ser fechado por soma silenciosa com skipna. O groupby(min_count=1)
    # preserva ausências, e a checagem de cobertura abaixo bloqueia o fechamento.
    colunas_soma = COLUNAS_DEMOGRAFIA
    por_municipio = work.groupby("codigo_ibge", as_index=False)[colunas_soma].sum(min_count=1)

    faltas_setoriais = work.groupby("codigo_ibge")[colunas_soma].apply(lambda x: x.isna().any().any())
    ruins = faltas_setoriais[faltas_setoriais].index.astype(str).tolist()
    if ruins:
        raise ValueError(
            "Há valores ausentes nas variáveis necessárias em setores dos municípios: " + ", ".join(ruins)
        )

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
