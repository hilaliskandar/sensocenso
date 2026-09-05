"""Etapa 09 em modo de fontes públicas correntes.

A identidade dos 8.073 setores e a topologia Queen são invariantes históricos
rígidos. A disponibilidade atual de PRIV_C3 e o Moran são recalculados com a
edição corrente; eventuais perdas temáticas são documentadas como deriva, sem
alterar o checkpoint territorial nem imputar valores históricos.
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

from .config import carregar_parametros
from .etapa09 import (
    EXPECTED_CROSS_MUN,
    EXPECTED_EDGES,
    EXPECTED_INTEGRATED,
    EXPECTED_ISLANDS,
    EXPECTED_MORAN_N,
    HISTORICAL_C3_REFERENCE,
    MALHA_SP_URL,
    _arestas_unicas,
    _baixar_malha,
    _carregar_geometrias,
    _diagnostico_cobertura,
    _moran_por_transformacao,
    _queen,
)
from .paths import resolve_paths
from .proveniencia import registrar_arquivo, registrar_evento
from .universo_integrado import carregar_universo_integrado_canonico


def executar(raiz: Path) -> None:
    raiz = raiz.resolve()
    paths = resolve_paths(raiz)
    paths.create()
    manifesto = paths.manifests / "execucao.jsonl"
    parametros = carregar_parametros(raiz / "config/parametros.yml")
    qa_ref = parametros.get("qa_referencia", {})
    permutacoes = int(parametros["espacial"]["permutacoes_moran"])

    entrada = paths.processed / "setorial" / "base_familias_sensibilidade_p75_p80.parquet"
    if not entrada.exists():
        raise FileNotFoundError(f"Pré-requisito 09 ausente: {entrada}")
    base = pd.read_parquet(entrada)
    base["codigo_setor"] = base["codigo_setor"].astype("string").str.strip()
    if base["codigo_setor"].duplicated().any():
        raise AssertionError("Base analítica possui CD_SETOR duplicado antes da validação espacial.")
    obrigatorias = ["PRIV_C3", "POP_TOTAL", "DPPO", "FLAG_UNIVERSO_INTEGRADO", "codigo_ibge"]
    faltantes = [c for c in obrigatorias if c not in base.columns]
    if faltantes:
        raise ValueError(f"Base 08 sem colunas necessárias à validação espacial: {faltantes}")

    diagnostico = _diagnostico_cobertura(base)
    diagnostico["n_c3_referencia_historica"] = HISTORICAL_C3_REFERENCE
    diagnostico["delta_c3_vs_referencia_historica"] = diagnostico["n_c3"] - HISTORICAL_C3_REFERENCE
    diagnostico["status_edicao_c3"] = (
        "igual_referencia_historica"
        if diagnostico["n_c3"] == HISTORICAL_C3_REFERENCE
        else "edicao_corrente_diverge_da_referencia_historica"
    )
    if diagnostico["n_flag_integrado"] != EXPECTED_INTEGRATED:
        raise AssertionError(
            "Gate territorial recebido das etapas 07/08 divergiu: "
            f"{diagnostico['n_flag_integrado']} != {EXPECTED_INTEGRATED}"
        )

    checkpoint, checkpoint_meta = carregar_universo_integrado_canonico(
        paths.raw, esperado=EXPECTED_INTEGRATED
    )
    codigos_checkpoint = set(checkpoint["codigo_setor"].astype(str))
    flag = base["FLAG_UNIVERSO_INTEGRADO"].astype(bool)
    codigos_flag = set(base.loc[flag, "codigo_setor"].astype(str))
    apenas_checkpoint = sorted(codigos_checkpoint - codigos_flag)
    apenas_flag = sorted(codigos_flag - codigos_checkpoint)
    diverg_gate = len(apenas_checkpoint) + len(apenas_flag)
    if diverg_gate:
        raise AssertionError(
            "FLAG_UNIVERSO_INTEGRADO diverge do checkpoint Gate18G7F2: "
            f"n={diverg_gate}; apenas_checkpoint={apenas_checkpoint[:20]}; apenas_flag={apenas_flag[:20]}"
        )
    integrado = base.loc[flag].copy()
    ausentes_privacao = integrado.loc[integrado["PRIV_C3"].isna(), "codigo_setor"].astype(str).tolist()

    raw_dir = paths.raw / "ibge" / "censo2022" / "malha_setores"
    raw_dir.mkdir(parents=True, exist_ok=True)
    malha_zip = _baixar_malha(raw_dir / "SP_setores_CD2022.zip", manifesto)
    geometrias = _carregar_geometrias(malha_zip, set(integrado["codigo_setor"].astype(str)))
    faltantes_geometria = sorted(
        set(integrado["codigo_setor"].astype(str)) - set(geometrias["codigo_setor"].astype(str))
    )
    if faltantes_geometria:
        raise AssertionError(
            f"Setores integrados sem geometria na malha oficial: n={len(faltantes_geometria)}; "
            f"amostra={faltantes_geometria[:20]}"
        )

    espacial = geometrias.merge(integrado, on="codigo_setor", how="inner", validate="one_to_one")
    espacial = gpd.GeoDataFrame(espacial, geometry="geometry", crs=geometrias.crs)
    if len(espacial) != EXPECTED_INTEGRATED:
        raise AssertionError(f"Join geometria x checkpoint alterou o universo: {len(espacial)}")

    # Topologia é verificada sobre todos os 8.073 setores, independentemente da
    # disponibilidade temática da edição corrente.
    w_integrado = _queen(espacial)
    ilhas_historicas = sorted(str(x) for x in w_integrado.islands)
    arestas = _arestas_unicas(w_integrado)
    municipio = espacial.set_index("codigo_setor")["codigo_ibge"].astype(str).to_dict()
    arestas_cross = sum(municipio[a] != municipio[b] for a, b in arestas)
    invariantes = {
        "universo_integrado": int(len(espacial)),
        "ilhas_queen": int(len(ilhas_historicas)),
        "arestas_queen_unicas": int(len(arestas)),
        "arestas_cross_municipais": int(arestas_cross),
    }
    esperados = {
        "universo_integrado": EXPECTED_INTEGRATED,
        "ilhas_queen": EXPECTED_ISLANDS,
        "arestas_queen_unicas": EXPECTED_EDGES,
        "arestas_cross_municipais": EXPECTED_CROSS_MUN,
    }
    divergencias_topologia = {
        k: {"observado": invariantes[k], "esperado": v}
        for k, v in esperados.items() if invariantes[k] != v
    }
    if divergencias_topologia:
        raise AssertionError(
            "Topologia Queen não reproduziu os invariantes auditados; "
            f"divergencias={divergencias_topologia}. Não corrigir manualmente."
        )

    ilhas_path = paths.qa / "etapa09_ilhas_queen_8073.csv"
    pd.DataFrame({"codigo_setor": ilhas_historicas}).to_csv(ilhas_path, index=False, encoding="utf-8")
    registrar_arquivo(manifesto, ilhas_path, origem="Etapa 09 corrente - ilhas Queen")

    # O Moran corrente exige valor temático observado. Primeiro retiram-se as
    # 177 ilhas históricas; depois os setores sem PRIV_C3 na edição corrente.
    candidatos = espacial.loc[
        ~espacial["codigo_setor"].astype(str).isin(ilhas_historicas)
        & espacial["PRIV_C3"].notna()
    ].copy()
    w_candidatos = _queen(candidatos)
    ilhas_induzidas = sorted(str(x) for x in w_candidatos.islands)
    moran_base = candidatos.loc[
        ~candidatos["codigo_setor"].astype(str).isin(ilhas_induzidas)
    ].copy()
    # Se a remoção de ilhas induzidas criar novas ilhas, a edição corrente não
    # pode ser comparada diretamente sem novo diagnóstico explícito.
    w_final = _queen(moran_base)
    if w_final.islands:
        raise AssertionError(
            "A ausência temática corrente gerou ilhas Queen em cascata após a primeira remoção: "
            f"amostra={w_final.islands[:20]}"
        )

    seed = 20260830
    moran_r = _moran_por_transformacao(moran_base, "r", permutacoes, seed=seed)
    moran_b = _moran_por_transformacao(moran_base, "b", permutacoes, seed=seed)
    ref_i = float(qa_ref.get("moran_privacao_aprox", 0.3507))
    ref_p = float(qa_ref.get("moran_pvalor", 0.002))
    for resultado in (moran_r, moran_b):
        resultado["delta_I_referencia"] = float(resultado["I"]) - ref_i
        resultado["delta_p_referencia"] = float(resultado["p_sim"]) - ref_p

    comparacao_moran_n = {
        "observado_corrente": int(len(moran_base)),
        "referencia_historica": EXPECTED_MORAN_N,
        "delta": int(len(moran_base)) - EXPECTED_MORAN_N,
    }
    deriva_tematicos = bool(ausentes_privacao) or comparacao_moran_n["delta"] != 0
    status = (
        "OK_COM_DERIVA_EDICAO_E_PENDENCIA_TRANSFORMACAO_MORAN"
        if deriva_tematicos
        else "OK_COM_PENDENCIA_TRANSFORMACAO_MORAN"
    )

    out_dir = paths.processed / "espacial"
    out_dir.mkdir(parents=True, exist_ok=True)
    gpkg_path = out_dir / "base_integrada_espacial_8073.gpkg"
    parquet_path = out_dir / "base_integrada_espacial_8073.parquet"
    espacial.to_file(gpkg_path, layer="setores", driver="GPKG")
    espacial.to_parquet(parquet_path, index=False)
    registrar_arquivo(manifesto, gpkg_path, origem="Etapa 09 corrente - malha + checkpoint")
    registrar_arquivo(manifesto, parquet_path, origem="Etapa 09 corrente - malha + checkpoint")

    qa = {
        "status": status,
        "etapa": "09",
        "modo_execucao": "fontes_correntes_com_checkpoint_historico",
        "fonte_malha": MALHA_SP_URL,
        "crs_malha": str(espacial.crs),
        "checkpoint_universo_integrado": checkpoint_meta,
        "diagnostico_cobertura_corrente": diagnostico,
        "divergencias_gate_07_09": diverg_gate,
        "invariantes_topologicos": invariantes,
        "setores_checkpoint_sem_privacao_na_edicao_corrente": ausentes_privacao,
        "n_setores_checkpoint_sem_privacao_na_edicao_corrente": len(ausentes_privacao),
        "ilhas_induzidas_por_ausencia_tematicas": ilhas_induzidas,
        "n_ilhas_induzidas_por_ausencia_tematicas": len(ilhas_induzidas),
        "comparacao_universo_moran": comparacao_moran_n,
        "moran_corrente_candidatos": {"row_standardized": moran_r, "binary": moran_b},
        "referencia_moran_historica": {"I_aprox": ref_i, "p_sim": ref_p, "n": EXPECTED_MORAN_N},
        "politica_deriva": (
            "Topologia e pertencimento territorial são gates rígidos. Ausência ou revisão de PRIV_C3 na edição "
            "corrente reduz apenas o universo estatístico corrente e é registrada, sem imputação histórica."
        ),
        "pendencia_moran": (
            "Recuperar do artefato computacional histórico a transformação/normalização canônica dos pesos "
            "antes de declarar reprodução numérica bit a bit."
        ),
        "saidas": [
            str(gpkg_path.relative_to(paths.data_root)),
            str(parquet_path.relative_to(paths.data_root)),
            str(ilhas_path.relative_to(paths.data_root)),
        ],
    }
    qa_path = paths.qa / "etapa09_validacao_espacial.json"
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    registrar_arquivo(manifesto, qa_path, origem="Etapa 09 corrente - QA espacial")
    registrar_evento(manifesto, {
        "tipo": "etapa", "etapa": "09", "status": status, "modo": qa["modo_execucao"],
        "universo_integrado": int(len(espacial)), "universo_moran_corrente": int(len(moran_base)),
        "n_privacao_ausente_checkpoint": len(ausentes_privacao),
    })
    print(json.dumps(qa, ensure_ascii=False, indent=2))
