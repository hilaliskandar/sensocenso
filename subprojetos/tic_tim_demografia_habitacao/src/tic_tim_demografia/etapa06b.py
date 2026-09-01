from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .etapa05c import (
    _arquivo_por_url,
    _coluna,
    _ler_csv_zip,
    _numero,
    _preparar_setor,
    _proporcao,
    _validar_01,
)
from .paths import resolve_paths
from .proveniencia import registrar_arquivo, registrar_evento

UNIVERSOS = ("domicilios", "moradores", "faces")
F3_ATRIBUTOS = (
    "bueiro_boca_de_lobo",
    "calcada",
    "pavimentacao",
    "iluminacao_publica",
    "arborizacao",
)
TODOS_ATRIBUTOS = F3_ATRIBUTOS + (
    "rampa_cadeirante",
    "obstaculo_calcada",
    "ponto_onibus",
    "infraestrutura_cicloviaria",
)
CHAVES_SETORIAIS = {
    "domicilios": ("CD_setor", "setor"),
    "moradores": ("CD_setor", "setor"),
    "faces": ("COD_SETOR_M22FINAL", "CD_setor", "setor"),
}


def _soma_completa(df: pd.DataFrame, codigos: list[str], rotulo: str) -> pd.Series:
    if not codigos:
        return pd.Series(np.nan, index=df.index, dtype="float64", name=rotulo)
    partes = [_numero(df[_coluna(df, codigo)], codigo).rename(codigo) for codigo in codigos]
    tab = pd.concat(partes, axis=1)
    return tab.sum(axis=1, min_count=len(partes)).rename(rotulo)


def _calcular_atributo(df: pd.DataFrame, regra: dict, prefixo: str) -> pd.DataFrame:
    sim = _soma_completa(df, list(regra["sim"]), f"{prefixo}_sim")
    nao = _soma_completa(df, list(regra["nao"]), f"{prefixo}_nao")
    nd = _soma_completa(df, list(regra.get("nao_declarado", [])), f"{prefixo}_nao_declarado")
    den = sim + nao
    pct_sim = 100.0 * _proporcao(sim, den)
    pct_nao = 100.0 * _proporcao(nao, den)
    _validar_01(pct_sim / 100.0, f"{prefixo}_pct_sim")
    _validar_01(pct_nao / 100.0, f"{prefixo}_pct_nao")
    return pd.DataFrame(
        {
            f"{prefixo}_sim": sim,
            f"{prefixo}_nao": nao,
            f"{prefixo}_nao_declarado": nd,
            f"{prefixo}_den_valido": den,
            f"{prefixo}_pct_sim": pct_sim,
            f"{prefixo}_pct_nao": pct_nao,
        },
        index=df.index,
    )


def _flag_p75(serie: pd.Series, p75: float) -> pd.Series:
    out = pd.Series(pd.NA, index=serie.index, dtype="Int64")
    valido = serie.notna()
    if abs(p75) <= 1e-12:
        out.loc[valido] = serie.loc[valido].gt(0).astype("int64")
    else:
        out.loc[valido] = serie.loc[valido].ge(p75).astype("int64")
    return out


def executar(raiz: Path) -> None:
    raiz = raiz.resolve()
    paths = resolve_paths(raiz)
    paths.create()
    manifesto = paths.manifests / "execucao.jsonl"

    qa06a_path = paths.qa / "etapa06a_gate_semantico_entorno.json"
    qa05b_path = paths.qa / "etapa05b_inspecao_fontes_isau.json"
    base_path = paths.processed / "setorial" / "base_isau_2022.parquet"
    for p in (qa06a_path, qa05b_path, base_path):
        if not p.exists():
            raise FileNotFoundError(f"Pré-requisito 06b ausente: {p}")

    qa06a = json.loads(qa06a_path.read_text(encoding="utf-8"))
    if qa06a.get("status") != "RESOLVIDO_ENTORNO":
        raise ValueError(f"Gate 06a não resolvido: status={qa06a.get('status')}")
    regras = qa06a["codigos_resolvidos"]
    qa05b = json.loads(qa05b_path.read_text(encoding="utf-8"))

    base = pd.read_parquet(base_path)
    canon = base[["codigo_setor", "codigo_ibge", "municipio"]].copy()
    canon["codigo_setor"] = canon["codigo_setor"].astype("string").str.strip()
    if canon["codigo_setor"].duplicated().any():
        raise ValueError("Base canônica 05c possui CD_SETOR duplicado.")
    idx = pd.Index(canon["codigo_setor"], name="codigo_setor")

    raw_ent = paths.raw / "ibge" / "censo2022" / "isau" / "entorno"
    blocos = []
    cobertura_fisica = {}
    for universo in UNIVERSOS:
        url = qa05b["arquivos_entorno"][universo]
        fonte = _preparar_setor(
            _ler_csv_zip(_arquivo_por_url(raw_ent, url)), *CHAVES_SETORIAIS[universo]
        )
        cobertura_fisica[universo] = int(fonte.index.isin(idx).sum())
        fonte = fonte.reindex(idx)
        for atributo in TODOS_ATRIBUTOS:
            regra = regras[atributo][universo]
            if not regra.get("confirmados_no_cabecalho"):
                raise ValueError(f"Código não confirmado no cabeçalho: {atributo}/{universo}")
            blocos.append(_calcular_atributo(fonte, regra, f"{universo}_{atributo}"))

    entorno = pd.concat(blocos, axis=1)
    entorno.insert(0, "codigo_setor", entorno.index.astype("string"))
    entorno = canon.merge(entorno.reset_index(drop=True), on="codigo_setor", how="left", validate="one_to_one")

    # F3: regra vigente do caderno público — agregado final segundo moradores.
    nomes_f3 = {
        "bueiro_boca_de_lobo": "moradores_bueiro_boca_de_lobo_pct_nao",
        "calcada": "moradores_calcada_pct_nao",
        "pavimentacao": "moradores_pavimentacao_pct_nao",
        "iluminacao_publica": "moradores_iluminacao_publica_pct_nao",
        "arborizacao": "moradores_arborizacao_pct_nao",
    }
    p75 = {atributo: float(entorno[col].dropna().quantile(0.75)) for atributo, col in nomes_f3.items()}
    flags = []
    for atributo, col in nomes_f3.items():
        f = _flag_p75(entorno[col], p75[atributo]).rename(f"F3_{atributo}_P75")
        entorno[f.name] = f
        flags.append(f)
    flagtab = pd.concat(flags, axis=1)
    entorno["F3_N_COMPONENTES_OBS"] = flagtab.notna().sum(axis=1).astype("Int64")
    entorno["F3_N_COMPONENTES_ALTOS"] = flagtab.sum(axis=1, min_count=1).astype("Int64")
    entorno["F3_ENTORNO_ALTO"] = pd.Series(pd.NA, index=entorno.index, dtype="Int64")
    completos = entorno["F3_N_COMPONENTES_OBS"].eq(len(F3_ATRIBUTOS))
    entorno.loc[completos, "F3_ENTORNO_ALTO"] = entorno.loc[completos, "F3_N_COMPONENTES_ALTOS"].ge(2).astype("int64")

    out_dir = paths.processed / "setorial"
    csv_path = out_dir / "base_entorno_urbano_2022.csv"
    parquet_path = out_dir / "base_entorno_urbano_2022.parquet"
    entorno.to_csv(csv_path, index=False, encoding="utf-8")
    entorno.to_parquet(parquet_path, index=False)
    registrar_arquivo(manifesto, csv_path, origem="Etapa 06b - entorno urbano Censo 2022")
    registrar_arquivo(manifesto, parquet_path, origem="Etapa 06b - entorno urbano Censo 2022")

    cobertura = {}
    for universo in UNIVERSOS:
        cobertura[universo] = {
            atributo: int(entorno[f"{universo}_{atributo}_pct_nao"].notna().sum())
            for atributo in TODOS_ATRIBUTOS
        }
    qa = {
        "status": "OK",
        "etapa": "06b",
        "universo": int(len(entorno)),
        "cobertura_fisica_fontes": cobertura_fisica,
        "cobertura_percentuais": cobertura,
        "f3": {
            "universo": "moradores",
            "componentes": nomes_f3,
            "p75": p75,
            "n_completos_5_componentes": int(completos.sum()),
            "n_entorno_alto": int(entorno["F3_ENTORNO_ALTO"].eq(1).sum()),
            "n_entorno_baixo": int(entorno["F3_ENTORNO_ALTO"].eq(0).sum()),
            "n_sem_classificacao": int(entorno["F3_ENTORNO_ALTO"].isna().sum()),
            "regra": (
                "F3=1 quando pelo menos 2 dos 5 percentuais de ausência segundo moradores atingem P75; "
                "se P75=0 exige valor >0. A classificação é emitida apenas com os 5 componentes observados."
            ),
        },
        "denominadores": (
            "Percentuais binários usam Sim+Não; Não declarado é excluído. Arborização usa Sem árvores / "
            "(Sem árvores + 1–2 + 3–4 + 5+ árvores), excluindo Saltado."
        ),
        "politica_ausencias": "sigilo, linha temática ausente ou categoria necessária ausente permanecem NaN",
        "saidas": [str(csv_path.relative_to(paths.data_root)), str(parquet_path.relative_to(paths.data_root))],
    }
    qa_path = paths.qa / "etapa06b_entorno_urbano.json"
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    registrar_arquivo(manifesto, qa_path, origem="Etapa 06b - QA entorno urbano")
    registrar_evento(manifesto, {"tipo": "etapa", "etapa": "06b", "status": "OK", "universo": int(len(entorno))})
    print(json.dumps(qa, ensure_ascii=False, indent=2))
