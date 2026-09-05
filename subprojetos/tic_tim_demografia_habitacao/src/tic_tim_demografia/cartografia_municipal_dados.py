from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from .etapa09 import _coluna_setor


DISPLAY_CRS = "EPSG:31983"
FAMILIAS_PUBLICAS = {
    "F1": "Formação e renovação de domicílios",
    "F2": "Melhoria ou substituição do estoque",
    "F3": "Urbanização e qualificação do entorno",
    "F4": "Adaptação do estoque às mudanças demográficas",
}


def crescimento(v0: pd.Series, v1: pd.Series) -> pd.Series:
    v0 = pd.to_numeric(v0, errors="coerce")
    v1 = pd.to_numeric(v1, errors="coerce")
    return (100.0 * (v1 / v0 - 1.0)).where(v0.gt(0))


def flag_integrado(serie: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(serie.dtype):
        return serie.fillna(False).astype(bool)
    return serie.astype("string").str.strip().str.casefold().isin(["true", "1"])


def predominancia_familias(familias: pd.DataFrame) -> pd.DataFrame:
    base = familias.copy()
    base["codigo_ibge"] = base["codigo_ibge"].astype("string")
    base = base.loc[flag_integrado(base["FLAG_UNIVERSO_INTEGRADO"])].copy()
    if base.empty:
        raise ValueError("M14 recebeu universo integrado vazio.")
    linhas: list[dict[str, object]] = []
    for codigo, grupo in base.groupby("codigo_ibge", sort=True):
        linha: dict[str, object] = {"codigo_ibge": str(codigo)}
        taxas: dict[str, float] = {}
        for familia in ("F1", "F2", "F3", "F4"):
            valores = pd.to_numeric(grupo[familia], errors="coerce")
            n = int(valores.notna().sum())
            taxa = np.nan if n == 0 else 100.0 * int(valores.eq(1).sum()) / n
            linha[f"pct_{familia.lower()}"] = taxa
            linha[f"n_obs_{familia.lower()}"] = n
            taxas[familia] = taxa
        validas = {k: v for k, v in taxas.items() if pd.notna(v)}
        if not validas:
            linha["M14"] = pd.NA
        else:
            maximo = max(validas.values())
            preds = [f for f, v in validas.items() if np.isclose(v, maximo, atol=1e-12, rtol=0.0)]
            linha["M14"] = "+".join(preds)
        linhas.append(linha)
    out = pd.DataFrame(linhas)
    if out["codigo_ibge"].duplicated().any():
        raise AssertionError("M14 produziu código municipal duplicado.")
    return out


def montar_dados_municipais(
    longitudinal: pd.DataFrame,
    renovacao: pd.DataFrame,
    sintese: pd.DataFrame,
    distributivas: pd.DataFrame,
    familias: pd.DataFrame,
) -> pd.DataFrame:
    long = longitudinal.copy()
    long["codigo_ibge"] = long["codigo_ibge"].astype("string")
    long["ano"] = pd.to_numeric(long["ano"], errors="coerce")
    p10 = long.loc[long["ano"].eq(2010)].set_index("codigo_ibge")
    p22 = long.loc[long["ano"].eq(2022)].set_index("codigo_ibge")
    codigos = p22.index.intersection(p10.index)
    out = pd.DataFrame(index=codigos)
    out["municipio"] = p22["municipio_config"].reindex(codigos).astype("string")
    out["M01"] = crescimento(p10["pop_total_harmonizada"].reindex(codigos), p22["pop_total_harmonizada"].reindex(codigos))
    out["M02"] = pd.to_numeric(p22["razao_envelhecimento"].reindex(codigos), errors="coerce")
    bases = [renovacao.copy(), sintese.copy(), distributivas.copy()]
    for base in bases:
        base["codigo_ibge"] = base["codigo_ibge"].astype("string")
    ren, sin, dis = [b.set_index("codigo_ibge") for b in bases]
    out["M03"] = pd.to_numeric(ren["cwr_0_4_por_1000_m1549"].reindex(codigos), errors="coerce")
    out["M05"] = 100.0 * pd.to_numeric(dis["pct_preta_parda_urbano"].reindex(codigos), errors="coerce")
    out["M10"] = 100.0 * pd.to_numeric(sin["agua_fora_rede"].reindex(codigos), errors="coerce")
    out["M11"] = 100.0 * pd.to_numeric(sin["esgotamento_inadequado"].reindex(codigos), errors="coerce")
    pred = predominancia_familias(familias).set_index("codigo_ibge")
    out = out.join(pred, how="left")
    out.index.name = "codigo_ibge"
    out = out.reset_index()
    if len(out) != 30 or out["codigo_ibge"].nunique() != 30:
        raise AssertionError(f"Cartografia municipal exige 30 municípios; obtidos={len(out)}")
    if out["municipio"].isna().any():
        raise AssertionError("Há município sem nome na base cartográfica municipal.")
    return out.sort_values("codigo_ibge").reset_index(drop=True)


def dissolver_setores_municipais(setores: gpd.GeoDataFrame, coluna_setor: str, codigos: set[str]) -> gpd.GeoDataFrame:
    codigos = {str(c).strip() for c in codigos}
    if setores.crs is None:
        raise ValueError("Malha oficial de setores sem CRS declarado.")
    if coluna_setor not in setores.columns:
        raise ValueError(f"Coluna setorial ausente na malha: {coluna_setor}")
    base = setores[[coluna_setor, "geometry"]].copy()
    base["codigo_setor"] = base[coluna_setor].astype("string").str.strip()
    base["codigo_ibge"] = base["codigo_setor"].str.slice(0, 7)
    base = base.loc[base["codigo_ibge"].isin(codigos), ["codigo_ibge", "geometry"]].copy()
    if base.empty:
        raise ValueError("Filtro da malha oficial não encontrou setores dos municípios solicitados.")
    invalidas = ~base.geometry.is_valid
    if invalidas.any():
        base.loc[invalidas, "geometry"] = base.loc[invalidas, "geometry"].make_valid()
    limites = base.dissolve(by="codigo_ibge", as_index=False)
    invalidas = ~limites.geometry.is_valid
    if invalidas.any():
        limites.loc[invalidas, "geometry"] = limites.loc[invalidas, "geometry"].make_valid()
    if (limites.geometry.is_empty | limites.geometry.isna()).any():
        raise ValueError("Dissolução municipal produziu geometria vazia ou nula.")
    faltantes = sorted(codigos - set(limites["codigo_ibge"].astype(str)))
    if faltantes:
        raise AssertionError(f"Dissolução municipal não cobriu todos os códigos solicitados; faltantes={faltantes}")
    return gpd.GeoDataFrame(limites, geometry="geometry", crs=base.crs)


def carregar_limites_municipais(path: Path, codigos: set[str]) -> gpd.GeoDataFrame:
    codigos = {str(c).strip() for c in codigos}
    if len(codigos) != 30:
        raise AssertionError(f"Geometria municipal exige 30 códigos; recebidos={len(codigos)}")
    filtro = " OR ".join(f"CD_SETOR LIKE '{codigo}%'" for codigo in sorted(codigos))
    try:
        setores = gpd.read_file(f"zip://{path}", columns=["CD_SETOR"], where=filtro)
        coluna = "CD_SETOR"
    except Exception:
        setores = gpd.read_file(f"zip://{path}")
        coluna = _coluna_setor(setores)
    limites = dissolver_setores_municipais(setores, coluna, codigos)
    if len(limites) != 30 or limites["codigo_ibge"].nunique() != 30:
        raise AssertionError(f"Dissolução municipal não fechou 30 territórios: n={len(limites)}")
    return limites


def classificar_quantis(serie: pd.Series, n_classes: int = 5, casas: int = 1) -> tuple[pd.Series, list[float], list[str]]:
    valores = pd.to_numeric(serie, errors="coerce")
    validos = valores.dropna()
    if validos.empty:
        raise ValueError("Classificação cartográfica recebeu série sem valores válidos.")
    q = min(n_classes, int(validos.nunique()))
    _, bins = pd.qcut(validos, q=q, retbins=True, duplicates="drop")
    bins = np.unique(np.asarray(bins, dtype="float64"))
    if len(bins) < 2:
        raise ValueError("Classificação cartográfica não produziu intervalos válidos.")
    rotulos = [f"{bins[i]:.{casas}f}–{bins[i + 1]:.{casas}f}" for i in range(len(bins) - 1)]
    classes = pd.cut(valores, bins=bins, labels=rotulos, include_lowest=True, right=True).astype("string")
    return classes, bins.tolist(), rotulos
