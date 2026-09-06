#!/usr/bin/env python3
"""Agrega os três arquivos oficiais de Entorno do Censo 2022 por APOND.

Fontes esperadas:
- Agregados_por_setores_entorno_domicílios_BR.csv (V05000-V05034)
- Agregados_por_setores_entorno_moradores_BR.csv (V05200-V05234)
- Agregados_por_setores_entorno_faces_BR.csv (V05400-V05434)

A rotina filtra os setores-alvo antes da agregação, preserva ausências como NA
e soma contadores por APOND. Também produz a linha MUNICIPIO pela soma dos
contadores das APONDs; percentuais são calculados somente na etapa seguinte.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


SERIES = {
    "domicilios": "V050",
    "moradores": "V052",
    "faces": "V054",
}


def normalizar_setor(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace(r"\.0$", "", regex=True).str.strip()


def carregar_matriz(path: Path, n_setores_esperados: int) -> pd.DataFrame:
    d = pd.read_csv(path, dtype=str)
    if not {"CD_SETOR", "APOND"}.issubset(d.columns):
        raise SystemExit("FAIL: matriz deve conter CD_SETOR e APOND")
    d = d[["CD_SETOR", "APOND"]].copy()
    d["CD_SETOR"] = normalizar_setor(d["CD_SETOR"])
    d["APOND"] = d["APOND"].astype(str).str.strip()
    if d["CD_SETOR"].duplicated().any():
        raise SystemExit("FAIL: CD_SETOR duplicado na matriz")
    if len(d) != n_setores_esperados:
        raise SystemExit(
            f"FAIL: esperados {n_setores_esperados} setores; matriz contém {len(d)}"
        )
    return d


def detectar_coluna_setor(colunas: list[str]) -> str:
    mapa = {str(c).strip().upper(): c for c in colunas}
    for candidato in ("SETOR", "CD_SETOR", "COD_SETOR_M22FINAL"):
        if candidato in mapa:
            return mapa[candidato]
    raise SystemExit(f"FAIL: coluna de setor não localizada: {colunas[:20]}")


def agregar_arquivo(
    path: Path,
    prefixo: str,
    matriz: pd.DataFrame,
    chunksize: int = 50000,
) -> tuple[pd.DataFrame, dict]:
    if not path.exists():
        raise SystemExit(f"FAIL: arquivo não encontrado: {path}")

    cab = pd.read_csv(path, sep=";", nrows=0, encoding="utf-8-sig")
    col_setor = detectar_coluna_setor(list(cab.columns))
    vars_ = [c for c in cab.columns if str(c).strip().upper().startswith(prefixo)]
    vars_ = sorted(vars_, key=lambda x: str(x).upper())
    esperadas = [f"{prefixo}{i:02d}" for i in range(35)]
    mapa_vars = {str(c).strip().upper(): c for c in vars_}
    faltantes = [v for v in esperadas if v not in mapa_vars]
    if faltantes:
        raise SystemExit(f"FAIL: {path.name} sem campos esperados: {faltantes}")

    usecols = [col_setor] + [mapa_vars[v] for v in esperadas]
    alvo = set(matriz["CD_SETOR"])
    partes = []
    n_linhas_lidas = 0
    n_linhas_alvo = 0
    valores_nao_numericos: dict[str, int] = {}

    for chunk in pd.read_csv(
        path,
        sep=";",
        usecols=usecols,
        dtype=str,
        encoding="utf-8-sig",
        chunksize=chunksize,
        low_memory=False,
    ):
        n_linhas_lidas += len(chunk)
        chunk[col_setor] = normalizar_setor(chunk[col_setor])
        chunk = chunk[chunk[col_setor].isin(alvo)].copy()
        if chunk.empty:
            continue
        n_linhas_alvo += len(chunk)
        chunk = chunk.rename(columns={col_setor: "CD_SETOR"})
        rename_vars = {mapa_vars[v]: v for v in esperadas}
        chunk = chunk.rename(columns=rename_vars)

        for v in esperadas:
            original = chunk[v].astype(str).str.strip()
            num = pd.to_numeric(original.str.replace(",", ".", regex=False), errors="coerce")
            inval = original.notna() & ~original.isin(["", "nan", "None"]) & num.isna()
            if inval.any():
                valores_nao_numericos[v] = valores_nao_numericos.get(v, 0) + int(inval.sum())
            chunk[v] = num
        partes.append(chunk[["CD_SETOR"] + esperadas])

    if not partes:
        raise SystemExit(f"FAIL: nenhum setor-alvo localizado em {path.name}")
    dados = pd.concat(partes, ignore_index=True)
    if dados["CD_SETOR"].duplicated().any():
        dups = dados.loc[dados["CD_SETOR"].duplicated(), "CD_SETOR"].unique().tolist()
        raise SystemExit(f"FAIL: setor duplicado em {path.name}: {dups[:10]}")

    encontrados = set(dados["CD_SETOR"])
    ausentes = sorted(alvo - encontrados)
    if ausentes:
        raise SystemExit(
            f"FAIL: {len(ausentes)} setores da matriz ausentes em {path.name}: {ausentes[:10]}"
        )

    dados = matriz.merge(dados, on="CD_SETOR", how="left", validate="one_to_one")
    agg = dados.groupby("APOND", sort=True)[esperadas].sum(min_count=1).reset_index()
    qa = {
        "arquivo": path.name,
        "prefixo": prefixo,
        "n_linhas_lidas": n_linhas_lidas,
        "n_setores_alvo": n_linhas_alvo,
        "n_setores_unicos": int(dados["CD_SETOR"].nunique()),
        "n_aponds": int(agg["APOND"].nunique()),
        "campos": esperadas,
        "valores_nao_numericos": valores_nao_numericos,
    }
    return agg, qa


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--domicilios", required=True, type=Path)
    p.add_argument("--moradores", required=True, type=Path)
    p.add_argument("--faces", required=True, type=Path)
    p.add_argument("--matriz", required=True, type=Path)
    p.add_argument("--saida", required=True, type=Path)
    p.add_argument("--qa", required=True, type=Path)
    p.add_argument("--n-setores-esperados", type=int, default=207)
    p.add_argument("--n-aponds-esperadas", type=int, default=7)
    args = p.parse_args()

    matriz = carregar_matriz(args.matriz, args.n_setores_esperados)
    arquivos = {
        "domicilios": args.domicilios,
        "moradores": args.moradores,
        "faces": args.faces,
    }

    resultado = None
    qa_fontes = {}
    for universo, prefixo in SERIES.items():
        agg, qa = agregar_arquivo(arquivos[universo], prefixo, matriz)
        qa_fontes[universo] = qa
        if resultado is None:
            resultado = agg
        else:
            resultado = resultado.merge(agg, on="APOND", how="outer", validate="one_to_one")

    assert resultado is not None
    if resultado["APOND"].nunique() != args.n_aponds_esperadas:
        raise SystemExit(
            f"FAIL: esperadas {args.n_aponds_esperadas} APONDs; obtidas {resultado['APOND'].nunique()}"
        )

    valor_cols = [c for c in resultado.columns if c != "APOND"]
    municipal = {"APOND": "MUNICIPIO"}
    for c in valor_cols:
        municipal[c] = pd.to_numeric(resultado[c], errors="coerce").sum(min_count=1)
    resultado = pd.concat([resultado, pd.DataFrame([municipal])], ignore_index=True)

    qa = {
        "status": "PASS",
        "n_setores_matriz": int(len(matriz)),
        "n_aponds": int(args.n_aponds_esperadas),
        "aponds": sorted(resultado.loc[resultado["APOND"] != "MUNICIPIO", "APOND"].astype(str).tolist()),
        "linha_municipal": True,
        "n_variaveis_entorno": len(valor_cols),
        "fontes": qa_fontes,
    }

    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.qa.parent.mkdir(parents=True, exist_ok=True)
    resultado.to_csv(args.saida, index=False, encoding="utf-8-sig")
    args.qa.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"PASS setores={qa['n_setores_matriz']} aponds={qa['n_aponds']} "
        f"variaveis={qa['n_variaveis_entorno']}"
    )
    print(args.saida)
    print(args.qa)


if __name__ == "__main__":
    main()
