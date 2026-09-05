"""Etapa 11c: cartografia municipal reprodutível TIC–TIM."""
from __future__ import annotations
import json
from pathlib import Path
import geopandas as gpd
import pandas as pd
from .cartografia_municipal_dados import DISPLAY_CRS, carregar_limites_municipais, classificar_quantis, montar_dados_municipais
from .cartografia_municipal_plot import plot_continuo, plot_m14
from .etapa09 import MALHA_SP_URL, _baixar_malha
from .paths import resolve_paths
from .proveniencia import registrar_arquivo, registrar_evento


def executar(raiz: Path) -> None:
    raiz = raiz.resolve(); paths = resolve_paths(raiz); paths.create(); manifesto = paths.manifests / "execucao.jsonl"
    arquivos = {
        "longitudinal": paths.processed / "municipal" / "base_longitudinal_2000_2010_2022.parquet",
        "renovacao": paths.processed / "municipal" / "base_renovacao_demografica_2022.parquet",
        "sintese": paths.processed / "municipal" / "base_sintese_municipal_2022.parquet",
        "distributivas": paths.processed / "municipal" / "base_camadas_distributivas_2022.parquet",
        "familias": paths.processed / "setorial" / "base_familias_analiticas_p75.parquet",
    }
    for nome, path in arquivos.items():
        if not path.exists(): raise FileNotFoundError(f"Pré-requisito 11c ausente ({nome}): {path}")
    dados = montar_dados_municipais(pd.read_parquet(arquivos["longitudinal"]), pd.read_parquet(arquivos["renovacao"]), pd.read_parquet(arquivos["sintese"]), pd.read_parquet(arquivos["distributivas"]), pd.read_parquet(arquivos["familias"]))
    raw_dir = paths.raw / "ibge" / "censo2022" / "malha_setores"; raw_dir.mkdir(parents=True, exist_ok=True)
    malha_zip = _baixar_malha(raw_dir / "SP_setores_CD2022.zip", manifesto)
    limites = carregar_limites_municipais(malha_zip, set(dados["codigo_ibge"].astype(str))); crs_fonte = str(limites.crs)
    mapa = limites.merge(dados, on="codigo_ibge", how="left", validate="one_to_one"); mapa = gpd.GeoDataFrame(mapa, geometry="geometry", crs=limites.crs)
    if mapa[["M01","M02","M03","M05","M10","M11"]].isna().all(axis=1).any(): raise AssertionError("Há município sem todos os indicadores cartográficos após integração.")
    mapa = mapa.to_crs(DISPLAY_CRS); qa_mapas: dict[str, object] = {}; saidas: list[Path] = []
    for codigo in ("M01","M02","M03","M05","M10","M11"):
        classe, _, _ = classificar_quantis(mapa[codigo]); mapa[f"classe_{codigo}"] = classe
        arqs, qa = plot_continuo(mapa, codigo, paths.maps); saidas.extend(arqs); qa_mapas[codigo] = qa
    arqs, qa = plot_m14(mapa, paths.maps); saidas.extend(arqs); qa_mapas["M14"] = qa
    data_dir = paths.output_data / "11c"; data_dir.mkdir(parents=True, exist_ok=True)
    colunas = ["codigo_ibge","municipio","M01","M02","M03","M05","M10","M11","M14","pct_f1","pct_f2","pct_f3","pct_f4","n_obs_f1","n_obs_f2","n_obs_f3","n_obs_f4","classe_M01","classe_M02","classe_M03","classe_M05","classe_M10","classe_M11"]
    dados_csv = data_dir / "base_cartografia_municipal_30.csv"; pd.DataFrame(mapa.drop(columns="geometry"))[colunas].to_csv(dados_csv, index=False, encoding="utf-8"); saidas.append(dados_csv)
    spatial = paths.processed / "espacial"; spatial.mkdir(parents=True, exist_ok=True); gpkg = spatial / "base_cartografia_municipal_30.gpkg"; parquet = spatial / "base_cartografia_municipal_30.parquet"
    mapa.to_file(gpkg, layer="municipios", driver="GPKG"); mapa.to_parquet(parquet, index=False); saidas.extend([gpkg, parquet])
    for path in saidas: registrar_arquivo(manifesto, path, origem="Etapa 11c — cartografia municipal reprodutível")
    qa_final = {"status":"OK","etapa":"11c","municipios":int(len(mapa)),"territorio_municipal_integral":True,"fonte_geometria":MALHA_SP_URL,"crs_fonte":crs_fonte,"crs_renderizacao":DISPLAY_CRS,"metodo_limite_municipal":"dissolve dos setores censitários 2022 por prefixo municipal de 7 dígitos","mapas":qa_mapas,"saidas":[str(p.relative_to(paths.data_root)) for p in saidas]}
    qa_path = paths.qa / "etapa11c_cartografia_municipal.json"; qa_path.write_text(json.dumps(qa_final, ensure_ascii=False, indent=2), encoding="utf-8"); registrar_arquivo(manifesto, qa_path, origem="Etapa 11c — QA cartográfico municipal")
    registrar_evento(manifesto, {"tipo":"etapa","etapa":"11c","status":"OK","municipios":int(len(mapa)),"mapas":7,"territorio_municipal_integral":True}); print(json.dumps(qa_final, ensure_ascii=False, indent=2))
