#!/usr/bin/env python3
"""Calcula as 30 distribuições do Entorno por APOND a partir de contadores agregados.

Entrada esperada: CSV produzido por agregar_entorno_apond.py, contendo uma linha
por APOND e a linha MUNICIPIO, com campos V050xx, V052xx e V054xx.

A semântica das categorias e do domínio aplicável é declarativa e vem de
config/tic_tim_entorno_regras.json. O script calcula percentual bruto sobre a
soma de todas as categorias da distribuição e percentual no domínio somente
sobre as categorias marcadas como aplicáveis. Categorias fora do domínio
recebem percentual de domínio ausente, nunca zero.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


COLUNAS_SAIDA = [
    "Tabela",
    "Característica",
    "Universo",
    "APOND",
    "Código",
    "Categoria",
    "Contagem agregada",
    "Percentual bruto (%)",
    "Percentual no domínio aplicável (%)",
    "Fora do domínio aplicável?",
    "Denominador observado",
    "Denominador no domínio aplicável",
    "Regra do domínio aplicável",
]


def carregar_config(path: Path) -> dict:
    cfg = json.loads(path.read_text(encoding="utf-8"))
    if set(cfg.get("universos", {})) != {"V050", "V052", "V054"}:
        raise SystemExit("FAIL: configuração deve conter universos V050, V052 e V054")
    tabelas = cfg.get("tabelas", {})
    esperadas = {f"E{i:02d}" for i in range(1, 11)}
    if set(tabelas) != esperadas:
        raise SystemExit(f"FAIL: configuração E01-E10 incompleta: {sorted(set(tabelas) ^ esperadas)}")
    return cfg


def pct(valor: float, den: float) -> float:
    if pd.isna(valor) or pd.isna(den) or den <= 0:
        return np.nan
    return float(valor) / float(den) * 100.0


def construir_longa(contadores: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    if "APOND" not in contadores.columns:
        raise SystemExit("FAIL: CSV de contadores sem coluna APOND")
    if contadores["APOND"].duplicated().any():
        raise SystemExit("FAIL: APOND duplicada no CSV de contadores")

    linhas = []
    for _, row in contadores.iterrows():
        apond = str(row["APOND"])
        for tabela, spec in cfg["tabelas"].items():
            for prefixo, universo in cfg["universos"].items():
                cats = spec["categorias"]
                codigos = [prefixo + c["sufixo"] for c in cats]
                faltantes = [c for c in codigos if c not in contadores.columns]
                if faltantes:
                    raise SystemExit(
                        f"FAIL: campos ausentes para {tabela}/{universo}: {faltantes}"
                    )

                valores = {
                    codigo: pd.to_numeric(pd.Series([row[codigo]]), errors="coerce").iloc[0]
                    for codigo in codigos
                }
                den_obs = pd.Series(list(valores.values()), dtype="float64").sum(min_count=1)
                codigos_app = [
                    prefixo + c["sufixo"] for c in cats if bool(c["aplicavel"])
                ]
                den_app = pd.Series(
                    [valores[c] for c in codigos_app], dtype="float64"
                ).sum(min_count=1)

                for cat in cats:
                    codigo = prefixo + cat["sufixo"]
                    valor = valores[codigo]
                    aplicavel = bool(cat["aplicavel"])
                    linhas.append(
                        {
                            "Tabela": tabela,
                            "Característica": spec["nome"],
                            "Universo": universo,
                            "APOND": apond,
                            "Código": codigo,
                            "Categoria": cat["categoria"],
                            "Contagem agregada": valor,
                            "Percentual bruto (%)": pct(valor, den_obs),
                            "Percentual no domínio aplicável (%)": (
                                pct(valor, den_app) if aplicavel else np.nan
                            ),
                            "Fora do domínio aplicável?": "NÃO" if aplicavel else "SIM",
                            "Denominador observado": den_obs,
                            "Denominador no domínio aplicável": den_app,
                            "Regra do domínio aplicável": spec["regra_dominio"],
                        }
                    )
    return pd.DataFrame(linhas, columns=COLUNAS_SAIDA)


def executar_qa(long: pd.DataFrame, n_aponds_esperadas: int | None) -> dict:
    erros = []
    territorios = sorted(long["APOND"].drop_duplicates().astype(str).tolist())
    aponds = [a for a in territorios if a != "MUNICIPIO"]
    if n_aponds_esperadas is not None and len(aponds) != n_aponds_esperadas:
        erros.append(
            f"esperadas {n_aponds_esperadas} APONDs; encontradas {len(aponds)}: {aponds}"
        )
    if "MUNICIPIO" not in territorios:
        erros.append("linha MUNICIPIO ausente")

    distribuicoes = long[["Tabela", "Universo"]].drop_duplicates()
    if len(distribuicoes) != 30:
        erros.append(f"esperadas 30 distribuições E×universo; encontradas {len(distribuicoes)}")

    max_desvio_bruto = 0.0
    max_desvio_dominio = 0.0
    grupos = long.groupby(["APOND", "Tabela", "Universo"], dropna=False)
    n_grupos = 0
    for chave, g in grupos:
        n_grupos += 1
        den_obs = pd.to_numeric(g["Denominador observado"], errors="coerce").iloc[0]
        den_app = pd.to_numeric(g["Denominador no domínio aplicável"], errors="coerce").iloc[0]

        if pd.notna(den_obs) and den_obs > 0:
            soma_bruto = pd.to_numeric(g["Percentual bruto (%)"], errors="coerce").sum()
            desvio = abs(float(soma_bruto) - 100.0)
            max_desvio_bruto = max(max_desvio_bruto, desvio)
            if desvio > 1e-8:
                erros.append(f"{chave}: soma percentual bruto={soma_bruto}")

        app = g[g["Fora do domínio aplicável?"] == "NÃO"]
        fora = g[g["Fora do domínio aplicável?"] == "SIM"]
        if fora["Percentual no domínio aplicável (%)"].notna().any():
            erros.append(f"{chave}: categoria fora do domínio com percentual de domínio preenchido")
        if pd.notna(den_app) and den_app > 0:
            soma_dom = pd.to_numeric(
                app["Percentual no domínio aplicável (%)"], errors="coerce"
            ).sum()
            desvio = abs(float(soma_dom) - 100.0)
            max_desvio_dominio = max(max_desvio_dominio, desvio)
            if desvio > 1e-8:
                erros.append(f"{chave}: soma percentual domínio={soma_dom}")

    esperado_grupos = len(territorios) * 30
    if n_grupos != esperado_grupos:
        erros.append(f"esperados {esperado_grupos} grupos território×distribuição; obtidos {n_grupos}")

    return {
        "status": "PASS" if not erros else "FAIL",
        "territorios": territorios,
        "aponds": aponds,
        "n_aponds": len(aponds),
        "linha_municipal": "MUNICIPIO" in territorios,
        "n_distribuicoes_por_territorio": 30,
        "n_grupos_qa": n_grupos,
        "max_desvio_soma_percentual_bruto": max_desvio_bruto,
        "max_desvio_soma_percentual_dominio": max_desvio_dominio,
        "erros": erros,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--contadores", required=True, type=Path)
    p.add_argument("--config", required=True, type=Path)
    p.add_argument("--saida", required=True, type=Path)
    p.add_argument("--qa", type=Path)
    p.add_argument("--n-aponds-esperadas", type=int, default=7)
    args = p.parse_args()

    if not args.contadores.exists():
        raise SystemExit(f"FAIL: contadores não encontrados: {args.contadores}")
    if not args.config.exists():
        raise SystemExit(f"FAIL: configuração não encontrada: {args.config}")

    contadores = pd.read_csv(args.contadores, dtype={"APOND": str})
    cfg = carregar_config(args.config)
    long = construir_longa(contadores, cfg)
    qa = executar_qa(long, args.n_aponds_esperadas)
    if qa["status"] != "PASS":
        raise SystemExit("FAIL QA: " + " | ".join(qa["erros"][:10]))

    args.saida.parent.mkdir(parents=True, exist_ok=True)
    long.to_csv(args.saida, index=False, encoding="utf-8-sig")
    qa_path = args.qa or args.saida.with_suffix(args.saida.suffix + ".qa.json")
    qa_path.parent.mkdir(parents=True, exist_ok=True)
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        f"PASS territorios={len(qa['territorios'])} aponds={qa['n_aponds']} "
        f"distribuicoes=30 grupos={qa['n_grupos_qa']}"
    )
    print(args.saida)
    print(qa_path)


if __name__ == "__main__":
    main()
