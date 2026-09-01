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


def executar(raiz: Path) -> None:
    raiz = raiz.resolve()
    paths = resolve_paths(raiz)
    paths.create()
    manifesto = paths.manifests / "execucao.jsonl"
    parametros = carregar_parametros(raiz / "config/parametros.yml")
    qa_ref = parametros.get("qa_referencia", {})
    esperado_final = int(qa_ref.get("setores_universo_final", 8073))
    permutacoes = int(parametros["espacial"]["permutacoes_moran"])

    entrada = paths.processed / "setorial" / "base_familias_sensibilidade_p75_p80.parquet"
    if not entrada.exists():
        raise FileNotFoundError(f"Pré-requisito 09 ausente: {entrada}. Execute primeiro --etapa 08.")
    base = pd.read_parquet(entrada)
    base["codigo_setor"] = base["codigo_setor"].astype("string").str.strip()
    if base["codigo_setor"].duplicated().any():
        raise AssertionError("Base analítica possui CD_SETOR duplicado antes da validação espacial.")

    # O fechamento espacial histórico parte do universo C3 observável. Setores sem
    # PRIV_C3 não entram no Moran e não podem definir contiguidade do indicador.
    candidato = base.loc[base["PRIV_C3"].notna()].copy()
    if len(candidato) != 8291:
        raise AssertionError(
            "Universo C3 antes da validação espacial divergiu do fechamento metodológico: "
            f"{len(candidato)} != 8291"
        )

    raw_dir = paths.raw / "ibge" / "censo2022" / "malha_setores"
    raw_dir.mkdir(parents=True, exist_ok=True)
    malha_zip = _baixar_malha(raw_dir / "SP_setores_CD2022.zip", manifesto)
    geometrias = _carregar_geometrias(malha_zip, set(candidato["codigo_setor"].astype(str)))

    faltantes_geometria = sorted(
        set(candidato["codigo_setor"].astype(str)) - set(geometrias["codigo_setor"].astype(str))
    )
    if faltantes_geometria:
        raise AssertionError(
            f"Setores C3 sem geometria na malha oficial: n={len(faltantes_geometria)}; "
            f"amostra={faltantes_geometria[:20]}"
        )

    espacial = geometrias.merge(candidato, on="codigo_setor", how="inner", validate="one_to_one")
    espacial = gpd.GeoDataFrame(espacial, geometry="geometry", crs=geometrias.crs)

    w_inicial = _queen(espacial)
    ilhas = sorted(str(x) for x in w_inicial.islands)
    ilhas_path = paths.qa / "etapa09_ilhas_queen_c3.csv"
    pd.DataFrame({"codigo_setor": ilhas}).to_csv(ilhas_path, index=False, encoding="utf-8")
    registrar_arquivo(manifesto, ilhas_path, origem="Etapa 09 - ilhas Queen no universo C3")

    final = espacial.loc[~espacial["codigo_setor"].astype(str).isin(ilhas)].copy()
    if len(final) != esperado_final:
        raise AssertionError(
            "Recorte espacial não reproduziu o universo final auditado: "
            f"C3={len(espacial)}, ilhas={len(ilhas)}, final={len(final)}, esperado={esperado_final}. "
            "Não ajustar o recorte manualmente; investigar geometria/vizinhança."
        )

    w = _queen(final)
    if w.islands:
        raise AssertionError(f"Persistem ilhas após o recorte espacial: {w.islands[:20]}")
    w.transform = "R"

    np.random.seed(20260830)
    valores = final.set_index("codigo_setor").loc[w.id_order, "PRIV_C3"].astype(float).to_numpy()
    moran = Moran(valores, w, permutations=permutacoes)

    ref_i = float(qa_ref.get("moran_privacao_aprox", 0.3507))
    ref_p = float(qa_ref.get("moran_pvalor", 0.002))
    if abs(float(moran.I) - ref_i) > 0.01:
        raise AssertionError(
            f"Moran I divergiu da referência auditada: {moran.I:.6f} vs ~{ref_i:.6f}"
        )
    if abs(float(moran.p_sim) - ref_p) > (1.0 / (permutacoes + 1) + 1e-12):
        raise AssertionError(
            f"p-valor simulado divergiu da referência auditada: {moran.p_sim:.6f} vs {ref_p:.6f}"
        )

    out_dir = paths.processed / "espacial"
    out_dir.mkdir(parents=True, exist_ok=True)
    gpkg_path = out_dir / "base_integrada_espacial_8073.gpkg"
    parquet_path = out_dir / "base_integrada_espacial_8073.parquet"
    final.to_file(gpkg_path, layer="setores", driver="GPKG")
    final.to_parquet(parquet_path, index=False)
    registrar_arquivo(manifesto, gpkg_path, origem="Etapa 09 - malha oficial IBGE + recorte Queen")
    registrar_arquivo(manifesto, parquet_path, origem="Etapa 09 - malha oficial IBGE + recorte Queen")

    qa = {
        "status": "OK",
        "etapa": "09",
        "fonte_malha": MALHA_SP_URL,
        "crs_malha": str(final.crs),
        "universo_urbano_amplo": int(len(base)),
        "universo_c3": int(len(candidato)),
        "geometrias_c3": int(len(espacial)),
        "ilhas_queen_removidas": int(len(ilhas)),
        "universo_final": int(len(final)),
        "regra_universo_final": "PRIV_C3 observável e pelo menos um vizinho Queen no universo C3",
        "moran_priv_c3": {
            "I": float(moran.I),
            "EI": float(moran.EI),
            "p_sim": float(moran.p_sim),
            "z_sim": float(moran.z_sim),
            "permutacoes": permutacoes,
            "transformacao_pesos": "R",
            "semente": 20260830,
        },
        "referencias": {
            "universo_final": esperado_final,
            "moran_I_aprox": ref_i,
            "moran_p": ref_p,
        },
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
            "status": "OK",
            "universo_final": int(len(final)),
            "moran_I": float(moran.I),
        },
    )
    print(json.dumps(qa, ensure_ascii=False, indent=2))
