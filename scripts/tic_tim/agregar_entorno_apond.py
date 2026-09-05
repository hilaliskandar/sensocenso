#!/usr/bin/env python3
"""Agrega os contadores do Entorno do Censo 2022 por APOND.

Regra metodológica: os contadores setoriais são somados primeiro; percentuais
são calculados somente após a agregação. O script não converte ausência ou
não aplicabilidade em zero e não calcula médias de percentuais setoriais.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


def ler_dbf(path: Path) -> pd.DataFrame:
    try:
        from dbfread import DBF
    except ImportError as exc:
        raise SystemExit("Instale dbfread: pip install dbfread") from exc
    return pd.DataFrame(iter(DBF(str(path), load=False, char_decode_errors="ignore")))


def normalizar_setor(s: pd.Series) -> pd.Series:
    return s.astype(str).str.replace(r"\\.0$", "", regex=True).str.zfill(15)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dbf", required=True, type=Path)
    p.add_argument("--matriz", required=True, type=Path, help="CSV/XLSX com CD_SETOR e APOND")
    p.add_argument("--saida", required=True, type=Path)
    p.add_argument("--cd-mun", default="3509007")
    args = p.parse_args()

    if args.matriz.suffix.lower() in {".xlsx", ".xls"}:
        m = pd.read_excel(args.matriz, dtype=str)
    else:
        m = pd.read_csv(args.matriz, dtype=str)
    if not {"CD_SETOR", "APOND"}.issubset(m.columns):
        raise SystemExit("Matriz deve conter CD_SETOR e APOND")
    m = m[["CD_SETOR", "APOND"]].dropna().copy()
    m["CD_SETOR"] = normalizar_setor(m["CD_SETOR"])
    m = m[m["CD_SETOR"].str.startswith(args.cd_mun)]
    if m["CD_SETOR"].duplicated().any():
        raise SystemExit("FAIL: CD_SETOR duplicado na matriz Setor→APOND")

    setores = set(m["CD_SETOR"])
    if args.cd_mun == "3509007" and len(setores) != 207:
        raise SystemExit(f"FAIL: Caieiras deveria ter 207 setores; encontrados {len(setores)}")

    d = ler_dbf(args.dbf)
    if "CD_SETOR" not in d.columns:
        raise SystemExit("FAIL: DBF sem CD_SETOR")
    d["CD_SETOR"] = normalizar_setor(d["CD_SETOR"])
    d = d[d["CD_SETOR"].isin(setores)].copy()
    encontrados = set(d["CD_SETOR"])
    faltantes = sorted(setores - encontrados)
    if faltantes:
        raise SystemExit(f"FAIL: {len(faltantes)} setores da matriz ausentes no DBF")

    x = d.merge(m, on="CD_SETOR", how="inner", validate="many_to_one")
    vars_entorno = [c for c in x.columns if c.startswith(("V050", "V052", "V054"))]
    if not vars_entorno:
        raise SystemExit("FAIL: nenhum campo V050xx/V052xx/V054xx localizado")
    for c in vars_entorno:
        x[c] = pd.to_numeric(x[c], errors="coerce")

    agg = x.groupby("APOND", as_index=False)[vars_entorno].sum(min_count=1)
    municipal = pd.DataFrame([{**{"APOND": "Caieiras"}, **{c: agg[c].sum(min_count=1) for c in vars_entorno}}])
    out = pd.concat([agg, municipal], ignore_index=True)
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.saida, index=False, encoding="utf-8-sig")
    print(f"PASS setores={len(encontrados)} aponds={agg['APOND'].nunique()} campos_entorno={len(vars_entorno)}")
    print(args.saida)


if __name__ == "__main__":
    main()
