from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from esda.moran import Moran
from libpysal.weights import Queen

from .config import carregar_parametros
from .fontes.http import HttpClient
from .paths import resolve_paths
from .proveniencia import registrar_arquivo, registrar_evento
from .universo_integrado import carregar_universo_integrado_canonico


MALHA_SP_URL = (
    "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/"
    "Agregados_por_Setores_Censitarios/malha_com_atributos/setores/shp/UF/SP/"
    "SP_setores_CD2022.zip"
)

# 8.291 e a cobertura C3 preservada no fechamento historico. As bases publicas
# do IBGE podem ser republicadas/revisadas; a pipeline corrente observou 8.312.
# Portanto 8.291 permanece como referencia de proveniencia, nao como gate duro.
HISTORICAL_C3_REFERENCE = 8291
EXPECTED_INTEGRATED = 8073
EXPECTED_ISLANDS = 177
EXPECTED_MORAN_N = 7896
EXPECTED_EDGES = 19314
EXPECTED_CROSS_MUN = 304


def _baixar_malha(destino: Path, manifesto: Path) -> Path:
    if destino.exists():
        return destino
    return HttpClient(timeout=900).baixar_arquivo(MALHA_SP_URL, destino, manifesto=manifesto)


def _coluna_setor(gdf: gpd.GeoDataFrame) -> str:
    mapa = {str(c).strip().casefold(): str(c) for c in gdf.columns}
    for candidato in ("cd_setor", "cdsetor", "codigo_setor"):
        if candidato in mapa:
            return mapa[candidato]
    raise ValueError(f"Malha IBGE sem codigo de setor reconhecivel: {list(gdf.columns)}")


def _carregar_geometrias(path: Path, setores: set[str]) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(f"zip://{path}")
    coluna = _coluna_setor(gdf)
    gdf["codigo_setor"] = gdf[coluna].astype("string").str.strip()
    gdf = gdf.loc[gdf["codigo_setor"].isin(setores), ["codigo_setor", "geometry"]].copy()
    if gdf["codigo_setor"].duplicated().any():
        raise AssertionError("Malha oficial possui codigo de setor duplicado no universo TIC-TIM.")
    if gdf.crs is None:
        raise ValueError("Malha oficial sem CRS declarado.")
    invalidas = ~gdf.geometry.is_valid
    if invalidas.any():
        gdf.loc[invalidas, "geometry"] = gdf.loc[invalidas, "geometry"].make_valid()
    vazias = gdf.geometry.is_empty | gdf.geometry.isna()
    if vazias.any():
        amostra = gdf.loc[vazias, "codigo_setor"].astype(str).tolist()[:20]
        raise ValueError(f"Geometrias vazias/nulas no universo analitico: {amostra}")
    return gdf


def _queen(gdf: gpd.GeoDataFrame) -> Queen:
    ids = gdf["codigo_setor"].astype(str).tolist()
    return Queen.from_dataframe(gdf, ids=ids, silence_warnings=True)


def _arestas_unicas(w: Queen) -> set[tuple[str, str]]:
    arestas: set[tuple[str, str]] = set()
    for origem, vizinhos in w.neighbors.items():
        for destino in vizinhos:
            a, b = sorted((str(origem), str(destino)))
            if a != b:
                arestas.add((a, b))
    return arestas


def _diagnostico_cobertura(base: pd.DataFrame) -> dict[str, int]:
    c3 = base["PRIV_C3"].notna()
    pop = base["POP_TOTAL"].notna()
    dppo = base["DPPO"].notna()
    return {
        "n_total": int(len(base)),
        "n_c3": int(c3.sum()),
        "n_c3_pop": int((c3 & pop).sum()),
        "n_c3_dppo": int((c3 & dppo).sum()),
        "n_c3_pop_dppo": int((c3 & pop & dppo).sum()),
        "n_pop": int(pop.sum()),
        "n_dppo": int(dppo.sum()),
        "n_flag_integrado": int(base["FLAG_UNIVERSO_INTEGRADO"].sum()),
    }


def _moran_por_transformacao(
    gdf: gpd.GeoDataFrame,
    transformacao: str,
    permutacoes: int,
    *,
    seed: int,
) -> dict[str, float | int | str]:
    w = _queen(gdf)
    if w.islands:
        raise AssertionError(f"Moran recebeu universo com ilhas: {w.islands[:20]}")
    valores = (
        gdf.set_index("codigo_setor")
        .loc[w.id_order, "PRIV_C3"]
        .astype(float)
        .to_numpy()
    )
    np.random.seed(seed)
    moran = Moran(
        valores,
        w,
        transformation=transformacao,
        permutations=permutacoes,
    )
    return {
        "transformacao": transformacao,
        "I": float(moran.I),
        "EI": float(moran.EI),
        "p_sim": float(moran.p_sim),
        "z_sim": float(moran.z_sim),
        "permutacoes": int(permutacoes),
        "semente": int(seed),
    }


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
        raise FileNotFoundError(f"Pre-requisito 09 ausente: {entrada}")

    base = pd.read_parquet(entrada)
    base["codigo_setor"] = base["codigo_setor"].astype("string").str.strip()
    if base["codigo_setor"].duplicated().any():
        raise AssertionError("Base analitica possui CD_SETOR duplicado antes da validacao espacial.")
    obrigatorias = ["PRIV_C3", "POP_TOTAL", "DPPO", "FLAG_UNIVERSO_INTEGRADO", "codigo_ibge"]
    faltantes = [c for c in obrigatorias if c not in base.columns]
    if faltantes:
        raise ValueError(f"Base 08 sem colunas necessarias a validacao espacial: {faltantes}")

    diagnostico = _diagnostico_cobertura(base)
    if diagnostico["n_c3"] < EXPECTED_INTEGRATED:
        raise AssertionError(
            "Cobertura C3 corrente e menor que o universo integrado canonico: "
            f"{diagnostico['n_c3']} < {EXPECTED_INTEGRATED}"
        )
    diagnostico["n_c3_referencia_historica"] = HISTORICAL_C3_REFERENCE
    diagnostico["delta_c3_vs_referencia_historica"] = (
        diagnostico["n_c3"] - HISTORICAL_C3_REFERENCE
    )
    diagnostico["status_edicao_c3"] = (
        "igual_referencia_historica"
        if diagnostico["n_c3"] == HISTORICAL_C3_REFERENCE
        else "edicao_corrente_diverge_da_referencia_historica"
    )

    if diagnostico["n_flag_integrado"] != EXPECTED_INTEGRATED:
        raise AssertionError(
            "Gate integrado recebido da etapa 07/08 divergiu: "
            f"{diagnostico['n_flag_integrado']} != {EXPECTED_INTEGRATED}"
        )

    checkpoint, checkpoint_meta = carregar_universo_integrado_canonico(
        paths.raw,
        esperado=EXPECTED_INTEGRATED,
    )
    codigos_checkpoint = set(checkpoint["codigo_setor"].astype(str))
    flag = base["FLAG_UNIVERSO_INTEGRADO"].astype(bool)
    codigos_flag = set(base.loc[flag, "codigo_setor"].astype(str))
    apenas_checkpoint = sorted(codigos_checkpoint - codigos_flag)
    apenas_flag = sorted(codigos_flag - codigos_checkpoint)
    diverg_gate = len(apenas_checkpoint) + len(apenas_flag)
    if diverg_gate:
        raise AssertionError(
            "FLAG_UNIVERSO_INTEGRADO diverge do checkpoint canonico Gate 18G7E: "
            f"n={diverg_gate}; apenas_checkpoint={apenas_checkpoint[:20]}; apenas_flag={apenas_flag[:20]}"
        )
    integrado = base.loc[flag].copy()
    if integrado["PRIV_C3"].isna().any():
        raise AssertionError("Universo integrado contem setor sem ISAU-C3, contrariando o Gate 18G7E.")

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
        raise AssertionError(
            f"Join geometria x universo integrado alterou o universo: {len(espacial)}"
        )

    w_integrado = _queen(espacial)
    ilhas = sorted(str(x) for x in w_integrado.islands)
    arestas = _arestas_unicas(w_integrado)
    municipio = espacial.set_index("codigo_setor")["codigo_ibge"].astype(str).to_dict()
    arestas_cross = sum(municipio[a] != municipio[b] for a, b in arestas)

    invariantes = {
        "universo_integrado": int(len(espacial)),
        "ilhas_queen": int(len(ilhas)),
        "arestas_queen_unicas": int(len(arestas)),
        "arestas_cross_municipais": int(arestas_cross),
    }
    esperados = {
        "universo_integrado": EXPECTED_INTEGRATED,
        "ilhas_queen": EXPECTED_ISLANDS,
        "arestas_queen_unicas": EXPECTED_EDGES,
        "arestas_cross_municipais": EXPECTED_CROSS_MUN,
    }
    divergencias = {
        k: {"observado": invariantes[k], "esperado": v}
        for k, v in esperados.items()
        if invariantes[k] != v
    }
    if divergencias:
        raise AssertionError(
            "Topologia Queen nao reproduziu os invariantes auditados; "
            f"divergencias={divergencias}. Nao corrigir manualmente."
        )

    ilhas_path = paths.qa / "etapa09_ilhas_queen_8073.csv"
    pd.DataFrame({"codigo_setor": ilhas}).to_csv(ilhas_path, index=False, encoding="utf-8")
    registrar_arquivo(manifesto, ilhas_path, origem="Etapa 09 - ilhas Queen no universo integrado")

    moran_base = espacial.loc[~espacial["codigo_setor"].astype(str).isin(ilhas)].copy()
    if len(moran_base) != EXPECTED_MORAN_N:
        raise AssertionError(
            f"Universo do Moran nao fechou: {len(moran_base)} != {EXPECTED_MORAN_N}"
        )

    # O caderno preserva o valor de referencia, mas registra que a transformacao
    # canonica da matriz de pesos deve ser recuperada do artefato computacional
    # original, nao inferida retrospectivamente. Calculam-se R e B como diagnostico.
    seed = 20260830
    moran_r = _moran_por_transformacao(moran_base, "r", permutacoes, seed=seed)
    moran_b = _moran_por_transformacao(moran_base, "b", permutacoes, seed=seed)
    ref_i = float(qa_ref.get("moran_privacao_aprox", 0.3507))
    ref_p = float(qa_ref.get("moran_pvalor", 0.002))
    for resultado in (moran_r, moran_b):
        resultado["delta_I_referencia"] = abs(float(resultado["I"]) - ref_i)
        resultado["delta_p_referencia"] = abs(float(resultado["p_sim"]) - ref_p)

    out_dir = paths.processed / "espacial"
    out_dir.mkdir(parents=True, exist_ok=True)
    gpkg_path = out_dir / "base_integrada_espacial_8073.gpkg"
    parquet_path = out_dir / "base_integrada_espacial_8073.parquet"
    espacial.to_file(gpkg_path, layer="setores", driver="GPKG")
    espacial.to_parquet(parquet_path, index=False)
    registrar_arquivo(manifesto, gpkg_path, origem="Etapa 09 - malha oficial IBGE + universo integrado")
    registrar_arquivo(manifesto, parquet_path, origem="Etapa 09 - malha oficial IBGE + universo integrado")

    qa = {
        "status": "OK_COM_PENDENCIA_TRANSFORMACAO_MORAN",
        "etapa": "09",
        "fonte_malha": MALHA_SP_URL,
        "crs_malha": str(espacial.crs),
        "gate_compatibilidade_tematica": (
            "checkpoint canonico Gate 18G7E: intersecao entre tipologia estrutural final e ISAU-C3"
        ),
        "checkpoint_universo_integrado": checkpoint_meta,
        "diagnostico_cobertura": diagnostico,
        "referencia_historica_c3": {
            "n_setores": HISTORICAL_C3_REFERENCE,
            "tratamento": (
                "Referencia do fechamento historico; divergencia da edicao publica corrente e "
                "registrada, mas nao redefine o Gate 18G7E de 8.073 setores."
            ),
        },
        "divergencias_gate_07_09": diverg_gate,
        "invariantes_topologicos": invariantes,
        "universo_moran": int(len(moran_base)),
        "moran_candidatos": {"row_standardized": moran_r, "binary": moran_b},
        "referencia_moran": {"I_aprox": ref_i, "p_sim": ref_p},
        "pendencia_moran": (
            "Recuperar do artefato computacional historico a transformacao/normalizacao canonica "
            "dos pesos antes de declarar reproducao numerica bit a bit."
        ),
        "saidas": [
            str(gpkg_path.relative_to(paths.data_root)),
            str(parquet_path.relative_to(paths.data_root)),
            str(ilhas_path.relative_to(paths.data_root)),
        ],
    }
    qa_path = paths.qa / "etapa09_validacao_espacial.json"
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    registrar_arquivo(manifesto, qa_path, origem="Etapa 09 - QA espacial")
    registrar_evento(
        manifesto,
        {
            "tipo": "etapa",
            "etapa": "09",
            "status": qa["status"],
            "universo_integrado": int(len(espacial)),
            "universo_moran": int(len(moran_base)),
            "n_c3_corrente": diagnostico["n_c3"],
            "n_c3_referencia_historica": HISTORICAL_C3_REFERENCE,
        },
    )
    print(json.dumps(qa, ensure_ascii=False, indent=2))
