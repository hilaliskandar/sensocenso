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


MALHA_SP_URL = (
    "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/"
    "Agregados_por_Setores_Censitarios/malha_com_atributos/setores/shp/UF/SP/"
    "SP_setores_CD2022.zip"
)

EXPECTED_C3 = 8291
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
    raise ValueError(f"Malha IBGE sem código de setor reconhecível: {list(gdf.columns)}")


def _carregar_geometrias(path: Path, setores: set[str]) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(f"zip://{path}")
    coluna = _coluna_setor(gdf)
    gdf["codigo_setor"] = gdf[coluna].astype("string").str.strip()
    gdf = gdf.loc[gdf["codigo_setor"].isin(setores), ["codigo_setor", "geometry"]].copy()
    if gdf["codigo_setor"].duplicated().any():
        raise AssertionError("Malha oficial possui código de setor duplicado no universo TIC–TIM.")
    if gdf.crs is None:
        raise ValueError("Malha oficial sem CRS declarado.")
    invalidas = ~gdf.geometry.is_valid
    if invalidas.any():
        gdf.loc[invalidas, "geometry"] = gdf.loc[invalidas, "geometry"].make_valid()
    vazias = gdf.geometry.is_empty | gdf.geometry.isna()
    if vazias.any():
        amostra = gdf.loc[vazias, "codigo_setor"].astype(str).tolist()[:20]
        raise ValueError(f"Geometrias vazias/nulas no universo analítico: {amostra}")
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
    exposicao_path = paths.processed / "setorial" / "base_isau_priorizacao_2022.parquet"
    for path in (entrada, exposicao_path):
        if not path.exists():
            raise FileNotFoundError(f"Pré-requisito 09 ausente: {path}")

    base = pd.read_parquet(entrada)
    base["codigo_setor"] = base["codigo_setor"].astype("string").str.strip()
    if base["codigo_setor"].duplicated().any():
        raise AssertionError("Base analítica possui CD_SETOR duplicado antes da validação espacial.")

    exposicao = pd.read_parquet(exposicao_path)[["codigo_setor", "POP_TOTAL", "DPPO"]].copy()
    exposicao["codigo_setor"] = exposicao["codigo_setor"].astype("string").str.strip()
    if exposicao["codigo_setor"].duplicated().any():
        raise AssertionError("Base de exposição 05e possui CD_SETOR duplicado.")
    base = base.merge(exposicao, on="codigo_setor", how="left", validate="one_to_one")

    diagnostico = _diagnostico_cobertura(base)
    if diagnostico["n_c3"] != EXPECTED_C3:
        raise AssertionError(
            "Universo C3 divergiu do fechamento metodológico: "
            f"{diagnostico['n_c3']} != {EXPECTED_C3}"
        )

    # Gate de compatibilidade temática do universo integrado. Esta hipótese é
    # explicitamente testada contra a referência auditada: C3 observável +
    # exposição populacional + domicílios ocupados observáveis. Se não fechar
    # exatamente em 8.073, a execução para com o diagnóstico e NÃO remove casos
    # arbitrariamente para alcançar a contagem histórica.
    integrado = base.loc[
        base["PRIV_C3"].notna()
        & base["POP_TOTAL"].notna()
        & base["DPPO"].notna()
    ].copy()
    if len(integrado) != EXPECTED_INTEGRATED:
        raise AssertionError(
            "Hipótese executável do universo integrado não reproduziu 8.073 setores. "
            f"diagnostico={diagnostico}. É necessário recuperar o gate histórico de "
            "compatibilidade temática; não ajustar a amostra manualmente."
        )

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
            f"Join geometria × universo integrado alterou o universo: {len(espacial)}"
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
            "Topologia Queen não reproduziu os invariantes auditados; "
            f"divergencias={divergencias}. Não corrigir manualmente."
        )

    ilhas_path = paths.qa / "etapa09_ilhas_queen_8073.csv"
    pd.DataFrame({"codigo_setor": ilhas}).to_csv(ilhas_path, index=False, encoding="utf-8")
    registrar_arquivo(manifesto, ilhas_path, origem="Etapa 09 - ilhas Queen no universo integrado")

    moran_base = espacial.loc[
        ~espacial["codigo_setor"].astype(str).isin(ilhas)
    ].copy()
    if len(moran_base) != EXPECTED_MORAN_N:
        raise AssertionError(
            f"Universo do Moran não fechou: {len(moran_base)} != {EXPECTED_MORAN_N}"
        )

    # O caderno preserva o valor de referência, mas registra que a transformação
    # canônica da matriz de pesos deve ser recuperada do artefato computacional
    # original, não inferida retrospectivamente. Por isso são calculadas e
    # registradas as especificações R e B; nenhuma é promovida a canônica apenas
    # por proximidade numérica com o resultado histórico.
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
            "PRIV_C3, POP_TOTAL e DPPO simultaneamente observáveis; gate aceito somente se reproduzir 8.073"
        ),
        "diagnostico_cobertura": diagnostico,
        "invariantes_topologicos": invariantes,
        "universo_moran": int(len(moran_base)),
        "moran_candidatos": {"row_standardized": moran_r, "binary": moran_b},
        "referencia_moran": {"I_aprox": ref_i, "p_sim": ref_p},
        "pendencia_moran": (
            "Recuperar do artefato computacional histórico a transformação/normalização canônica "
            "dos pesos antes de declarar reprodução numérica bit a bit."
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
        },
    )
    print(json.dumps(qa, ensure_ascii=False, indent=2))
