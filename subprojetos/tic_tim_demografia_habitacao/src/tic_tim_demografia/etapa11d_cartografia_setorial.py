"""Etapa 11d: cartografia setorial e prancha do entorno TIC–TIM."""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

from .cartografia_municipal_dados import DISPLAY_CRS
from .cartografia_setorial_dados import (
    M12_COMPONENTES,
    categorizar_m08,
    categorizar_m09,
    classificar_quantis_setoriais,
    classificar_zero_mais_quantis,
    preparar_m12,
    selecionar_insets_m04,
    selecionar_insets_m06,
    selecionar_insets_m08,
    validar_integrado,
)
from .cartografia_setorial_plot import (
    plot_continuo_com_insets,
    plot_m08,
    plot_m09,
    plot_m12,
)
from .etapa09 import MALHA_SP_URL, _baixar_malha, _carregar_geometrias
from .paths import resolve_paths
from .proveniencia import registrar_arquivo, registrar_evento


REFERENCIAS_HISTORICAS = {
    "M08_convergentes_p75": 1255,
    "M09_persistentes_p75_p80": 959,
    "M09_mesmo_vetor": 886,
}


def _registrar_csv_m04(base: gpd.GeoDataFrame, destino: Path) -> Path:
    classes, _, _ = classificar_quantis_setoriais(
        base["cwr_0_4_por_1000_m1549"], n_classes=5, casas=1
    )
    out = pd.DataFrame(base.drop(columns="geometry"))[
        ["codigo_setor", "codigo_ibge", "municipio", "cwr_0_4_por_1000_m1549"]
    ].copy()
    out["classe"] = classes
    path = destino / "M04_renovacao_geracional_setorial.csv"
    out.to_csv(path, index=False, encoding="utf-8")
    return path


def _registrar_csv_m06(base: gpd.GeoDataFrame, destino: Path) -> Path:
    classes, _, _ = classificar_quantis_setoriais(base["PRIV_C3"], n_classes=5, casas=3)
    out = pd.DataFrame(base.drop(columns="geometry"))[
        ["codigo_setor", "codigo_ibge", "municipio", "PRIV_C3"]
    ].copy()
    out["classe"] = classes
    path = destino / "M06_privacao_sanitario_ambiental_setorial.csv"
    out.to_csv(path, index=False, encoding="utf-8")
    return path


def _registrar_csv_m08(base: gpd.GeoDataFrame, destino: Path) -> Path:
    cols = [
        "codigo_setor",
        "codigo_ibge",
        "municipio",
        "N_FAMILIAS_SINAL",
        "N_FAMILIAS_OBSERVADAS",
        "CONVERGENCIA_3_OU_4",
    ]
    out = pd.DataFrame(base.drop(columns="geometry"))[cols].copy()
    out["categoria"] = categorizar_m08(base)
    path = destino / "M08_necessidades_combinadas_p75.csv"
    out.to_csv(path, index=False, encoding="utf-8")
    return path


def _registrar_csv_m09(base: gpd.GeoDataFrame, destino: Path) -> Path:
    cols = [
        "codigo_setor",
        "codigo_ibge",
        "municipio",
        "CONVERGENCIA_3_OU_4",
        "CONVERGENCIA_3_OU_4_P80",
        "PERSISTENTE_P75_P80",
        "MESMO_VETOR_P75_P80",
    ]
    out = pd.DataFrame(base.drop(columns="geometry"))[cols].copy()
    out["categoria"] = categorizar_m09(base)
    path = destino / "M09_estabilidade_p75_p80.csv"
    out.to_csv(path, index=False, encoding="utf-8")
    return path


def _registrar_csv_m12(base: gpd.GeoDataFrame, destino: Path) -> Path:
    out = pd.DataFrame(base.drop(columns="geometry"))[
        ["codigo_setor", "codigo_ibge", "municipio"] + list(M12_COMPONENTES.values())
    ].copy()
    for chave, coluna in M12_COMPONENTES.items():
        classes, _, _ = classificar_zero_mais_quantis(
            out[coluna], n_classes_positivas=4, casas=1
        )
        out[f"classe_{chave}"] = classes
    path = destino / "M12_carencias_entorno_cinco_componentes.csv"
    out.to_csv(path, index=False, encoding="utf-8")
    return path


def executar(raiz: Path) -> None:
    raiz = raiz.resolve()
    paths = resolve_paths(raiz)
    paths.create()
    manifesto = paths.manifests / "execucao.jsonl"

    arquivos = {
        "integrado_8073": paths.processed / "espacial" / "base_integrada_espacial_8073.gpkg",
        "limites_30": paths.processed / "espacial" / "base_cartografia_municipal_30.gpkg",
        "entorno_9087": paths.processed / "setorial" / "base_entorno_urbano_2022.parquet",
    }
    for nome, path in arquivos.items():
        if not path.exists():
            raise FileNotFoundError(f"Pré-requisito 11d ausente ({nome}): {path}")

    integrado = validar_integrado(gpd.read_file(arquivos["integrado_8073"], layer="setores"))
    if integrado.crs is None:
        raise ValueError("Base espacial integrada 8.073 sem CRS declarado.")
    crs_fonte_integrado = str(integrado.crs)
    limites = gpd.read_file(arquivos["limites_30"], layer="municipios")
    if limites.crs is None:
        raise ValueError("Limites municipais da etapa 11c sem CRS declarado.")
    limites["codigo_ibge"] = limites["codigo_ibge"].astype("string").str.strip()
    if len(limites) != 30 or limites["codigo_ibge"].nunique() != 30:
        raise AssertionError("Etapa 11d exige 30 limites municipais únicos da etapa 11c.")

    integrado = integrado.to_crs(DISPLAY_CRS)
    limites = limites.to_crs(DISPLAY_CRS)
    mapas_dir = paths.maps
    data_dir = paths.output_data / "11d"
    data_dir.mkdir(parents=True, exist_ok=True)
    saidas: list[Path] = []
    qa_mapas: dict[str, object] = {}

    insets_m04 = selecionar_insets_m04(integrado)
    arqs, qa = plot_continuo_com_insets(
        integrado,
        limites,
        codigo="M04",
        coluna="cwr_0_4_por_1000_m1549",
        insets=insets_m04,
        destino=mapas_dir,
        unidade="crianças 0–4 / mil mulheres 15–49",
        casas=1,
        nota=(
            "Proxy censitária: crianças de 0–4 anos por mil mulheres de 15–49 anos. "
            "Setores sem informação aparecem em cinza; insets selecionados pelo maior intervalo interquartil municipal."
        ),
    )
    saidas.extend(arqs)
    qa_mapas["M04"] = qa
    saidas.append(_registrar_csv_m04(integrado, data_dir))

    insets_m06 = selecionar_insets_m06(integrado)
    arqs, qa = plot_continuo_com_insets(
        integrado,
        limites,
        codigo="M06",
        coluna="PRIV_C3",
        insets=insets_m06,
        destino=mapas_dir,
        unidade="índice relativo 0–1",
        casas=3,
        nota=(
            "PRIV_C3 = 1 − ISAU_C3; valores maiores indicam maior privação sanitário-ambiental. "
            "ISAU_C3 combina abastecimento de água, esgotamento, resíduos e drenagem quando ao menos três domínios são observados; não mede isoladamente a condição física da unidade."
        ),
    )
    saidas.extend(arqs)
    qa_mapas["M06"] = qa
    saidas.append(_registrar_csv_m06(integrado, data_dir))

    insets_m08 = selecionar_insets_m08(integrado)
    arqs, qa = plot_m08(
        integrado,
        limites,
        insets_m08,
        mapas_dir,
        referencia_historica=REFERENCIAS_HISTORICAS["M08_convergentes_p75"],
    )
    saidas.extend(arqs)
    qa_mapas["M08"] = qa
    saidas.append(_registrar_csv_m08(integrado, data_dir))

    arqs, qa = plot_m09(
        integrado,
        limites,
        mapas_dir,
        referencia_persistentes=REFERENCIAS_HISTORICAS["M09_persistentes_p75_p80"],
    )
    qa["referencia_historica_mesmo_vetor"] = REFERENCIAS_HISTORICAS["M09_mesmo_vetor"]
    qa["delta_mesmo_vetor"] = (
        int(qa["mesmo_vetor_corrente"]) - REFERENCIAS_HISTORICAS["M09_mesmo_vetor"]
    )
    saidas.extend(arqs)
    qa_mapas["M09"] = qa
    saidas.append(_registrar_csv_m09(integrado, data_dir))

    entorno = preparar_m12(pd.read_parquet(arquivos["entorno_9087"]))
    raw_dir = paths.raw / "ibge" / "censo2022" / "malha_setores"
    raw_dir.mkdir(parents=True, exist_ok=True)
    malha_zip = _baixar_malha(raw_dir / "SP_setores_CD2022.zip", manifesto)
    geometrias = _carregar_geometrias(malha_zip, set(entorno["codigo_setor"].astype(str)))
    faltantes_geometria = sorted(
        set(entorno["codigo_setor"].astype(str)) - set(geometrias["codigo_setor"].astype(str))
    )
    if faltantes_geometria:
        raise AssertionError(
            "M12 possui setores sem geometria oficial: "
            f"n={len(faltantes_geometria)}; amostra={faltantes_geometria[:20]}"
        )
    m12_cols = ["codigo_setor", "codigo_ibge", "municipio"] + list(M12_COMPONENTES.values())
    entorno_geo = geometrias.merge(
        entorno[m12_cols], on="codigo_setor", how="inner", validate="one_to_one"
    )
    entorno_geo = gpd.GeoDataFrame(entorno_geo, geometry="geometry", crs=geometrias.crs)
    if len(entorno_geo) != 9087:
        raise AssertionError(f"Join cartográfico M12 alterou universo: {len(entorno_geo)} != 9087")
    crs_fonte_m12 = str(entorno_geo.crs)

    spatial = paths.processed / "espacial"
    spatial.mkdir(parents=True, exist_ok=True)
    gpkg_m12 = spatial / "base_cartografia_entorno_9087.gpkg"
    parquet_m12 = spatial / "base_cartografia_entorno_9087.parquet"
    entorno_geo.to_file(gpkg_m12, layer="setores", driver="GPKG")
    entorno_geo.to_parquet(parquet_m12, index=False)
    saidas.extend([gpkg_m12, parquet_m12])

    entorno_plot = entorno_geo.to_crs(DISPLAY_CRS)
    arqs, qa = plot_m12(entorno_plot, limites, mapas_dir)
    saidas.extend(arqs)
    qa_mapas["M12"] = qa
    saidas.append(_registrar_csv_m12(entorno_plot, data_dir))

    esperados = {
        "M04_validos": 7474,
        "M06_validos": 8067,
        "M08_convergentes": 1304,
        "M09_persistentes": 1016,
        "M09_mesmo_vetor": 945,
        "M12_universo": 9087,
        "M12_validos_por_componente": 8557,
    }
    observados = {
        "M04_validos": int(qa_mapas["M04"]["n_validos"]),
        "M06_validos": int(qa_mapas["M06"]["n_validos"]),
        "M08_convergentes": int(qa_mapas["M08"]["convergentes_correntes"]),
        "M09_persistentes": int(qa_mapas["M09"]["persistentes_correntes"]),
        "M09_mesmo_vetor": int(qa_mapas["M09"]["mesmo_vetor_corrente"]),
        "M12_universo": int(qa_mapas["M12"]["universo_setorial"]),
    }
    for chave, valor in esperados.items():
        if chave == "M12_validos_por_componente":
            encontrados = {
                k: int(v["n_validos"])
                for k, v in qa_mapas["M12"]["componentes"].items()
            }
            if set(encontrados.values()) != {valor}:
                raise AssertionError(
                    f"Cobertura M12 divergiu do fechamento corrente: {encontrados}"
                )
            observados[chave] = encontrados
        elif observados[chave] != valor:
            raise AssertionError(
                f"Invariante 11d divergiu em {chave}: {observados[chave]} != {valor}"
            )

    for path in saidas:
        registrar_arquivo(manifesto, path, origem="Etapa 11d — cartografia setorial reprodutível")

    qa_final = {
        "status": "OK_COM_DERIVA_EDICAO",
        "etapa": "11d",
        "fonte_geometria": MALHA_SP_URL,
        "crs_fonte_integrado": crs_fonte_integrado,
        "crs_fonte_m12": crs_fonte_m12,
        "crs_renderizacao": DISPLAY_CRS,
        "universo_integrado": 8073,
        "universo_entorno": 9087,
        "politica_edicao": (
            "M08 e M09 representam os resultados correntes do pipeline. As referências "
            "históricas 1.255/959/886 permanecem apenas como QA e não são metas de calibração."
        ),
        "referencias_historicas": REFERENCIAS_HISTORICAS,
        "invariantes_correntes": observados,
        "mapas": qa_mapas,
        "saidas": [str(p.relative_to(paths.data_root)) for p in saidas],
    }
    qa_path = paths.qa / "etapa11d_cartografia_setorial.json"
    qa_path.write_text(json.dumps(qa_final, ensure_ascii=False, indent=2), encoding="utf-8")
    registrar_arquivo(manifesto, qa_path, origem="Etapa 11d — QA cartográfico setorial")
    registrar_evento(
        manifesto,
        {
            "tipo": "etapa",
            "etapa": "11d",
            "status": qa_final["status"],
            "mapas": 5,
            "universo_integrado": 8073,
            "universo_entorno": 9087,
            "convergentes_p75_correntes": observados["M08_convergentes"],
            "persistentes_p75_p80_correntes": observados["M09_persistentes"],
        },
    )
    print(json.dumps(qa_final, ensure_ascii=False, indent=2))
