from __future__ import annotations

import json
import math
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import pandas as pd

from .etapa05c import _arquivo_por_url, _coluna, _ler_csv_zip, _numero, _preparar_setor
from .paths import resolve_paths
from .proveniencia import registrar_arquivo, registrar_evento


PCTS = (0.10, 0.05, 0.01)
REFERENCIA_LEGADA = {
    "n_c3": 8291,
    "corr_carga_pop_dom_pearson": 0.9884429602,
    "q75_def": 0.1591100663,
    "q75_pop": 620.0,
    "q75_dppo": 226.0,
    "top10_intersec_def_carga_pop": 375,
    "top10_jaccard_def_carga_pop": 0.292,
    "top05_intersec_def_carga_pop": 148,
    "top05_jaccard_def_carga_pop": 0.217,
    "top01_intersec_def_carga_pop": 22,
    "top01_jaccard_def_carga_pop": 0.153,
}


def _top_ids(df: pd.DataFrame, coluna: str, pct: float) -> set[str]:
    validos = df.loc[df[coluna].notna(), ["codigo_setor", coluna]].copy()
    n = max(1, int(math.ceil(len(validos) * pct)))
    return set(
        validos.sort_values([coluna, "codigo_setor"], ascending=[False, True])
        .head(n)["codigo_setor"]
        .astype(str)
    )


def _jaccard(a: set[str], b: set[str]) -> float:
    uniao = a | b
    return float(len(a & b) / len(uniao)) if uniao else float("nan")


def _classe_quadrante(deficit: pd.Series, escala: pd.Series, qdef: float, qesc: float) -> pd.Series:
    out = pd.Series(pd.NA, index=deficit.index, dtype="string")
    valid = deficit.notna() & escala.notna()
    alta_g = deficit.ge(qdef)
    alta_e = escala.ge(qesc)
    out.loc[valid & alta_g & alta_e] = "ALTA_GRAVIDADE_ALTA_ESCALA"
    out.loc[valid & alta_g & ~alta_e] = "ALTA_GRAVIDADE_BAIXA_ESCALA"
    out.loc[valid & ~alta_g & alta_e] = "BAIXA_GRAVIDADE_ALTA_ESCALA"
    out.loc[valid & ~alta_g & ~alta_e] = "BAIXA_GRAVIDADE_BAIXA_ESCALA"
    return out


def executar(raiz: Path) -> None:
    raiz = raiz.resolve()
    paths = resolve_paths(raiz)
    paths.create()
    manifesto = paths.manifests / "execucao.jsonl"

    base_path = paths.processed / "setorial" / "base_isau_2022.parquet"
    renov_path = paths.processed / "setorial" / "base_renovacao_demografica_2022.parquet"
    qa05b_path = paths.qa / "etapa05b_inspecao_fontes_isau.json"
    for p in (base_path, renov_path, qa05b_path):
        if not p.exists():
            raise FileNotFoundError(f"Pré-requisito 05e ausente: {p}")

    base = pd.read_parquet(base_path)
    renov = pd.read_parquet(renov_path)
    qa05b = json.loads(qa05b_path.read_text(encoding="utf-8"))

    for c in ("codigo_setor", "codigo_ibge", "municipio", "ISAU_C3", "N_DOMINIOS_OBS", "DOMINIO_AUSENTE"):
        if c not in base.columns:
            raise ValueError(f"Base 05c sem coluna obrigatória: {c}")
    if "V01006" not in renov.columns:
        raise ValueError("Base da etapa 04 sem V01006 (população total).")

    pop = renov[["codigo_setor", "V01006"]].copy()
    pop["codigo_setor"] = pop["codigo_setor"].astype("string").str.strip()
    pop["POP_TOTAL"] = pd.to_numeric(pop["V01006"], errors="coerce")
    pop = pop[["codigo_setor", "POP_TOTAL"]]

    # DPPO é reobtido do arquivo oficial Características do domicílio 1 para não
    # depender de artefato legado. O denominador é V00001, conforme Gate 18G7B.
    urls_dom = list(qa05b["arquivos_domiciliares"])
    dom1_url = next(u for u in urls_dom if "domicilio1" in Path(urlparse(u).path).name.casefold())
    raw_dom = paths.raw / "ibge" / "censo2022" / "isau" / "domicilios"
    dom1 = _preparar_setor(_ler_csv_zip(_arquivo_por_url(raw_dom, dom1_url)), "CD_setor", "setor")
    dppo = pd.DataFrame(
        {
            "codigo_setor": dom1.index.astype("string"),
            "DPPO": _numero(dom1[_coluna(dom1, "V00001")], "V00001").to_numpy(),
        }
    )

    work = (
        base.merge(pop, on="codigo_setor", how="left", validate="one_to_one")
        .merge(dppo, on="codigo_setor", how="left", validate="one_to_one")
    )
    work["DEF_C3"] = 1.0 - work["ISAU_C3"]
    work["CARGA_POP_C3"] = work["DEF_C3"] * work["POP_TOTAL"]
    work["CARGA_DOM_C3"] = work["DEF_C3"] * work["DPPO"]

    popmax = float(work["POP_TOTAL"].max(skipna=True))
    dppomax = float(work["DPPO"].max(skipna=True))
    work["EXP_POP_LOGN"] = np.log1p(work["POP_TOTAL"]) / np.log1p(popmax)
    work["EXP_DOM_LOGN"] = np.log1p(work["DPPO"]) / np.log1p(dppomax)
    work["PRIOR_POP_GEO"] = np.sqrt(work["DEF_C3"] * work["EXP_POP_LOGN"])
    work["PRIOR_DOM_GEO"] = np.sqrt(work["DEF_C3"] * work["EXP_DOM_LOGN"])
    work["RANK_CARGA_POP"] = work["CARGA_POP_C3"].rank(method="min", ascending=False)
    work["RANK_CARGA_DOM"] = work["CARGA_DOM_C3"].rank(method="min", ascending=False)

    c3 = work.loc[work["ISAU_C3"].notna()].copy()
    q75_def = float(c3["DEF_C3"].quantile(0.75))
    q75_pop = float(c3["POP_TOTAL"].quantile(0.75))
    q75_dppo = float(c3["DPPO"].quantile(0.75))
    work["CLASSE_GRAV_ESCALA_POP"] = _classe_quadrante(
        work["DEF_C3"], work["POP_TOTAL"], q75_def, q75_pop
    )
    work["CLASSE_GRAV_ESCALA_DOM"] = _classe_quadrante(
        work["DEF_C3"], work["DPPO"], q75_def, q75_dppo
    )

    comparacoes = {}
    for pct in PCTS:
        chave = f"top_{int(pct*100):02d}"
        conjuntos = {
            "DEF_C3": _top_ids(c3, "DEF_C3", pct),
            "CARGA_POP_C3": _top_ids(c3, "CARGA_POP_C3", pct),
            "CARGA_DOM_C3": _top_ids(c3, "CARGA_DOM_C3", pct),
            "PRIOR_POP_GEO": _top_ids(c3, "PRIOR_POP_GEO", pct),
            "PRIOR_DOM_GEO": _top_ids(c3, "PRIOR_DOM_GEO", pct),
        }
        comparacoes[chave] = {
            "n_alvo": len(conjuntos["DEF_C3"]),
            "def_x_carga_pop_intersecao": len(conjuntos["DEF_C3"] & conjuntos["CARGA_POP_C3"]),
            "def_x_carga_pop_jaccard": _jaccard(conjuntos["DEF_C3"], conjuntos["CARGA_POP_C3"]),
            "def_x_carga_dom_intersecao": len(conjuntos["DEF_C3"] & conjuntos["CARGA_DOM_C3"]),
            "def_x_carga_dom_jaccard": _jaccard(conjuntos["DEF_C3"], conjuntos["CARGA_DOM_C3"]),
            "def_x_prior_pop_intersecao": len(conjuntos["DEF_C3"] & conjuntos["PRIOR_POP_GEO"]),
            "def_x_prior_pop_jaccard": _jaccard(conjuntos["DEF_C3"], conjuntos["PRIOR_POP_GEO"]),
            "def_x_prior_dom_intersecao": len(conjuntos["DEF_C3"] & conjuntos["PRIOR_DOM_GEO"]),
            "def_x_prior_dom_jaccard": _jaccard(conjuntos["DEF_C3"], conjuntos["PRIOR_DOM_GEO"]),
        }

    corr_pearson = float(c3[["CARGA_POP_C3", "CARGA_DOM_C3"]].corr(method="pearson").iloc[0, 1])
    corr_spearman = float(c3[["CARGA_POP_C3", "CARGA_DOM_C3"]].corr(method="spearman").iloc[0, 1])
    corr_pop_dppo = float(c3[["POP_TOTAL", "DPPO"]].corr(method="pearson").iloc[0, 1])

    colunas_saida = [
        "codigo_setor", "codigo_ibge", "municipio", "POP_TOTAL", "DPPO", "ISAU_C3", "DEF_C3",
        "CARGA_POP_C3", "CARGA_DOM_C3", "EXP_POP_LOGN", "EXP_DOM_LOGN", "PRIOR_POP_GEO",
        "PRIOR_DOM_GEO", "RANK_CARGA_POP", "RANK_CARGA_DOM", "CLASSE_GRAV_ESCALA_POP",
        "CLASSE_GRAV_ESCALA_DOM", "N_DOMINIOS_OBS", "DOMINIO_AUSENTE",
    ]
    out = work[colunas_saida].copy()
    out_dir = paths.processed / "setorial"
    csv_path = out_dir / "base_isau_priorizacao_2022.csv"
    parquet_path = out_dir / "base_isau_priorizacao_2022.parquet"
    out.to_csv(csv_path, index=False, encoding="utf-8")
    out.to_parquet(parquet_path, index=False)
    registrar_arquivo(manifesto, csv_path, origem="Gate 05e/G7D corrigido")
    registrar_arquivo(manifesto, parquet_path, origem="Gate 05e/G7D corrigido")

    qa = {
        "status": "OK",
        "etapa": "05e",
        "objetivo": "reexecutar Gate 18G7D de ponderação por exposição sobre ISAU corrigido",
        "n_c3": int(len(c3)),
        "formulas": {
            "DEF_C3": "1 - ISAU_C3",
            "CARGA_POP_C3": "DEF_C3 * POP_TOTAL",
            "CARGA_DOM_C3": "DEF_C3 * DPPO",
            "EXP_POP_LOGN": "ln(1+POP_TOTAL)/ln(1+POP_TOTAL_max)",
            "EXP_DOM_LOGN": "ln(1+DPPO)/ln(1+DPPO_max)",
            "PRIOR_POP_GEO": "sqrt(DEF_C3 * EXP_POP_LOGN)",
            "PRIOR_DOM_GEO": "sqrt(DEF_C3 * EXP_DOM_LOGN)",
        },
        "q75": {"DEF_C3": q75_def, "POP_TOTAL": q75_pop, "DPPO": q75_dppo},
        "correlacoes": {
            "carga_pop_x_carga_dom_pearson": corr_pearson,
            "carga_pop_x_carga_dom_spearman": corr_spearman,
            "pop_x_dppo_pearson": corr_pop_dppo,
        },
        "extremos": comparacoes,
        "referencia_legada_g7d": REFERENCIA_LEGADA,
        "nota_referencia_legada": (
            "A referência histórica é comparativa, não gate de igualdade, pois deriva do ISAU com drenagem legada desalinhada."
        ),
        "regra_interpretacao": (
            "ISAU/DEF mede condição/gravidade; cargas medem magnitude social; PRIOR_GEO é stress test de compromisso. "
            "Nenhuma dessas medidas substitui as demais."
        ),
        "saidas": [
            str(csv_path.relative_to(paths.data_root)),
            str(parquet_path.relative_to(paths.data_root)),
        ],
    }
    qa_path = paths.qa / "etapa05e_ponderacao_exposicao_isau.json"
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    registrar_arquivo(manifesto, qa_path, origem="Gate 05e/G7D corrigido")
    registrar_evento(manifesto, {"tipo": "etapa", "etapa": "05e", "status": "OK", "n_c3": int(len(c3))})
    print(json.dumps(qa, ensure_ascii=False, indent=2))
