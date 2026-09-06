#!/usr/bin/env python3
"""Agrega contadores do Entorno do Censo 2022 por APOND.

Princípios:
- filtrar os setores-alvo durante a leitura do DBF, sem carregar a base estadual
  inteira em memória;
- somar contadores setoriais primeiro e calcular percentuais apenas em etapa
  posterior, após aplicação explícita das regras de domínio;
- nunca converter ausência/não aplicabilidade em zero;
- produzir QA reproduzível do recorte e dos campos encontrados.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import pandas as pd

PREFIXOS_ENTORNO = ("V050", "V052", "V054")


def normalizar_codigo_setor(valor: object) -> str:
    s = str(valor).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s.zfill(15)


def carregar_matriz(path: Path, cd_mun: str) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        m = pd.read_excel(path, dtype=str)
    else:
        m = pd.read_csv(path, dtype=str)
    if not {"CD_SETOR", "APOND"}.issubset(m.columns):
        raise SystemExit("FAIL: matriz deve conter CD_SETOR e APOND")
    m = m[["CD_SETOR", "APOND"]].dropna().copy()
    m["CD_SETOR"] = m["CD_SETOR"].map(normalizar_codigo_setor)
    m["APOND"] = m["APOND"].astype(str).str.strip()
    m = m[m["CD_SETOR"].str.startswith(cd_mun)].copy()
    if m.empty:
        raise SystemExit(f"FAIL: nenhum setor localizado para CD_MUN={cd_mun}")
    if m["CD_SETOR"].duplicated().any():
        dup = m.loc[m["CD_SETOR"].duplicated(keep=False), "CD_SETOR"].tolist()[:10]
        raise SystemExit(f"FAIL: CD_SETOR duplicado na matriz Setor→APOND: {dup}")
    return m.sort_values(["APOND", "CD_SETOR"]).reset_index(drop=True)


def iterar_dbf_filtrado(path: Path, setores: set[str]) -> tuple[list[str], list[dict]]:
    try:
        from dbfread import DBF
    except ImportError as exc:
        raise SystemExit("Instale dbfread: pip install dbfread") from exc

    tabela = DBF(str(path), load=False, char_decode_errors="ignore")
    campos = list(tabela.field_names)
    if "CD_SETOR" not in campos:
        raise SystemExit("FAIL: DBF sem CD_SETOR")

    vars_entorno = [c for c in campos if c.startswith(PREFIXOS_ENTORNO)]
    if not vars_entorno:
        raise SystemExit("FAIL: nenhum campo V050xx/V052xx/V054xx localizado")

    manter = {"CD_SETOR", *vars_entorno}
    registros: list[dict] = []
    for row in tabela:
        setor = normalizar_codigo_setor(row.get("CD_SETOR"))
        if setor not in setores:
            continue
        registros.append({k: row.get(k) for k in manter})
    return vars_entorno, registros


def converter_numericos(df: pd.DataFrame, colunas: Iterable[str]) -> pd.DataFrame:
    out = df.copy()
    for c in colunas:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dbf", required=True, type=Path)
    p.add_argument("--matriz", required=True, type=Path, help="CSV/XLSX com CD_SETOR e APOND")
    p.add_argument("--saida", required=True, type=Path, help="CSV de contadores agregados por APOND")
    p.add_argument("--qa", type=Path, help="JSON de QA; padrão: <saida>.qa.json")
    p.add_argument("--cd-mun", default="3509007")
    p.add_argument("--n-setores-esperados", type=int, default=207)
    args = p.parse_args()

    if not args.dbf.exists():
        raise SystemExit(f"FAIL: DBF não encontrado: {args.dbf}")
    if not args.matriz.exists():
        raise SystemExit(f"FAIL: matriz não encontrada: {args.matriz}")

    m = carregar_matriz(args.matriz, args.cd_mun)
    setores = set(m["CD_SETOR"])
    if args.n_setores_esperados and len(setores) != args.n_setores_esperados:
        raise SystemExit(
            f"FAIL: esperados {args.n_setores_esperados} setores; encontrados {len(setores)}"
        )

    vars_entorno, registros = iterar_dbf_filtrado(args.dbf, setores)
    d = pd.DataFrame(registros)
    if d.empty:
        raise SystemExit("FAIL: nenhum setor-alvo encontrado no DBF")
    d["CD_SETOR"] = d["CD_SETOR"].map(normalizar_codigo_setor)

    encontrados = set(d["CD_SETOR"])
    faltantes = sorted(setores - encontrados)
    extras = sorted(encontrados - setores)
    if faltantes:
        raise SystemExit(f"FAIL: {len(faltantes)} setores da matriz ausentes no DBF")
    if extras:
        raise SystemExit(f"FAIL: {len(extras)} setores extras após filtragem")
    if d["CD_SETOR"].duplicated().any():
        raise SystemExit("FAIL: DBF contém mais de um registro por CD_SETOR no recorte")

    d = converter_numericos(d, vars_entorno)
    x = d.merge(m, on="CD_SETOR", how="inner", validate="one_to_one")

    agg = x.groupby("APOND", as_index=False)[vars_entorno].sum(min_count=1)
    aponds_esperadas = sorted(m["APOND"].unique().tolist())
    aponds_obtidas = sorted(agg["APOND"].unique().tolist())
    if aponds_obtidas != aponds_esperadas:
        raise SystemExit(
            f"FAIL: APONDs divergentes. esperadas={aponds_esperadas} obtidas={aponds_obtidas}"
        )

    municipal = {
        "APOND": "MUNICIPIO",
        **{c: agg[c].sum(min_count=1) for c in vars_entorno},
    }
    out = pd.concat([agg, pd.DataFrame([municipal])], ignore_index=True)

    args.saida.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.saida, index=False, encoding="utf-8-sig")

    qa_path = args.qa or args.saida.with_suffix(args.saida.suffix + ".qa.json")
    qa_path.parent.mkdir(parents=True, exist_ok=True)
    qa = {
        "status": "PASS",
        "cd_mun": args.cd_mun,
        "setores_esperados": args.n_setores_esperados,
        "setores_matriz": len(setores),
        "setores_dbf_recorte": len(encontrados),
        "aponds": aponds_obtidas,
        "n_aponds": len(aponds_obtidas),
        "campos_entorno": vars_entorno,
        "n_campos_entorno": len(vars_entorno),
        "regra": "contadores setoriais somados por APOND antes de qualquer percentual",
        "percentuais_calculados": False,
        "dominios_aplicados": False,
        "saida": str(args.saida),
    }
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        "PASS "
        f"setores={len(encontrados)} aponds={len(aponds_obtidas)} "
        f"campos_entorno={len(vars_entorno)}"
    )
    print(args.saida)
    print(qa_path)


if __name__ == "__main__":
    main()
