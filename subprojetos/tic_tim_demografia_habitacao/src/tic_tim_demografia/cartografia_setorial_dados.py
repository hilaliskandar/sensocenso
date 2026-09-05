from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


M12_COMPONENTES = {
    "drenagem": "moradores_bueiro_boca_de_lobo_pct_nao",
    "calcadas": "moradores_calcada_pct_nao",
    "pavimentacao": "moradores_pavimentacao_pct_nao",
    "arborizacao": "moradores_arborizacao_pct_nao",
    "iluminacao": "moradores_iluminacao_publica_pct_nao",
}


@dataclass(frozen=True)
class InsetSelecao:
    codigo_ibge: str
    municipio: str
    metrica: float


def classificar_quantis_setoriais(
    serie: pd.Series,
    *,
    n_classes: int = 5,
    casas: int = 1,
) -> tuple[pd.Series, list[float], list[str]]:
    valores = pd.to_numeric(serie, errors="coerce")
    validos = valores.dropna()
    if validos.empty:
        raise ValueError("Classificação setorial recebeu série sem valores válidos.")
    q = min(int(n_classes), int(validos.nunique()))
    if q < 1:
        raise ValueError("Classificação setorial sem valores distintos suficientes.")
    if q == 1:
        minimo = maximo = float(validos.iloc[0])
        rotulo = f"{minimo:.{casas}f}"
        classes = pd.Series(pd.NA, index=valores.index, dtype="string")
        classes.loc[valores.notna()] = rotulo
        return classes, [minimo, maximo], [rotulo]
    _, bins = pd.qcut(validos, q=q, retbins=True, duplicates="drop")
    bins = np.unique(np.asarray(bins, dtype="float64"))
    if len(bins) < 2:
        raise ValueError("Classificação setorial não produziu intervalos válidos.")
    rotulos = [
        f"{bins[i]:.{casas}f}–{bins[i + 1]:.{casas}f}"
        for i in range(len(bins) - 1)
    ]
    classes = pd.cut(
        valores,
        bins=bins,
        labels=rotulos,
        include_lowest=True,
        right=True,
    ).astype("string")
    return classes, bins.tolist(), rotulos


def classificar_zero_mais_quantis(
    serie: pd.Series,
    *,
    n_classes_positivas: int = 4,
    casas: int = 1,
) -> tuple[pd.Series, list[float], list[str]]:
    """Separa ausência observada (0) dos quantis entre valores positivos.

    Essa classificação é usada na prancha M12 porque, em alguns componentes do
    entorno, a massa em zero supera 75% dos setores. Um qcut direto colapsaria
    classes e ocultaria a variação dos eventos positivos raros.
    """
    valores = pd.to_numeric(serie, errors="coerce")
    validos = valores.dropna()
    if validos.empty:
        raise ValueError("Classificação zero+quantis recebeu série sem valores válidos.")
    if (validos < 0).any():
        raise ValueError("Classificação zero+quantis exige valores não negativos.")
    out = pd.Series(pd.NA, index=valores.index, dtype="string")
    rotulos: list[str] = []
    limites: list[float] = [0.0]
    zeros = valores.eq(0)
    if zeros.any():
        out.loc[zeros] = "0"
        rotulos.append("0")
    positivos = valores.loc[valores.gt(0)].dropna()
    if positivos.empty:
        return out, limites, rotulos
    q = min(int(n_classes_positivas), int(positivos.nunique()))
    if q == 1:
        rotulo = f">0–{float(positivos.max()):.{casas}f}"
        out.loc[valores.gt(0)] = rotulo
        rotulos.append(rotulo)
        limites.extend([float(positivos.min()), float(positivos.max())])
        return out, sorted(set(limites)), rotulos
    _, bins = pd.qcut(positivos, q=q, retbins=True, duplicates="drop")
    bins = np.unique(np.asarray(bins, dtype="float64"))
    pos_rotulos = [
        f">0–{bins[i + 1]:.{casas}f}"
        if i == 0
        else f"{bins[i]:.{casas}f}–{bins[i + 1]:.{casas}f}"
        for i in range(len(bins) - 1)
    ]
    pos_classes = pd.cut(
        valores,
        bins=bins,
        labels=pos_rotulos,
        include_lowest=True,
        right=True,
    ).astype("string")
    out.loc[valores.gt(0)] = pos_classes.loc[valores.gt(0)]
    rotulos.extend(pos_rotulos)
    limites.extend(bins.tolist())
    return out, sorted(set(float(x) for x in limites)), rotulos


def validar_integrado(base: pd.DataFrame, esperado: int = 8073) -> pd.DataFrame:
    out = base.copy()
    out["codigo_setor"] = out["codigo_setor"].astype("string").str.strip()
    out["codigo_ibge"] = out["codigo_ibge"].astype("string").str.strip()
    if len(out) != esperado:
        raise AssertionError(
            f"Cartografia setorial exige {esperado} setores integrados; obtidos={len(out)}"
        )
    if out["codigo_setor"].duplicated().any():
        raise AssertionError("Cartografia setorial recebeu código de setor duplicado.")
    return out


def selecionar_insets_m04(base: pd.DataFrame, n: int = 3) -> list[InsetSelecao]:
    """Seleciona, de modo determinístico, municípios com maior IQR do CWR."""
    dados = base.copy()
    dados["cwr_0_4_por_1000_m1549"] = pd.to_numeric(
        dados["cwr_0_4_por_1000_m1549"], errors="coerce"
    )
    stats = (
        dados.groupby(["codigo_ibge", "municipio"], dropna=False)[
            "cwr_0_4_por_1000_m1549"
        ]
        .agg(n="count", q25=lambda s: s.quantile(0.25), q75=lambda s: s.quantile(0.75))
        .reset_index()
    )
    stats["metrica"] = stats["q75"] - stats["q25"]
    stats = stats.loc[stats["n"].gt(0) & stats["metrica"].notna()]
    stats = stats.sort_values(["metrica", "codigo_ibge"], ascending=[False, True]).head(n)
    return [
        InsetSelecao(str(r.codigo_ibge), str(r.municipio), float(r.metrica))
        for r in stats.itertuples(index=False)
    ]


def selecionar_insets_m06(base: pd.DataFrame, n: int = 3) -> list[InsetSelecao]:
    """Seleciona, de modo determinístico, maiores medianas municipais de PRIV_C3."""
    dados = base.copy()
    dados["PRIV_C3"] = pd.to_numeric(dados["PRIV_C3"], errors="coerce")
    stats = (
        dados.groupby(["codigo_ibge", "municipio"], dropna=False)["PRIV_C3"]
        .agg(n="count", metrica="median")
        .reset_index()
    )
    stats = stats.loc[stats["n"].gt(0) & stats["metrica"].notna()]
    stats = stats.sort_values(["metrica", "codigo_ibge"], ascending=[False, True]).head(n)
    return [
        InsetSelecao(str(r.codigo_ibge), str(r.municipio), float(r.metrica))
        for r in stats.itertuples(index=False)
    ]


def selecionar_insets_m08(base: pd.DataFrame, n: int = 3) -> list[InsetSelecao]:
    """Seleciona maiores percentuais municipais de convergência P75.

    O denominador é territorial: todos os setores integrados do município,
    inclusive classificações indeterminadas, conforme a regra da etapa 10/T06.
    """
    dados = base.copy()
    conv = pd.to_numeric(dados["CONVERGENCIA_3_OU_4"], errors="coerce")
    dados["_conv"] = conv.eq(1)
    stats = (
        dados.groupby(["codigo_ibge", "municipio"], dropna=False)
        .agg(n=("codigo_setor", "size"), convergentes=("_conv", "sum"))
        .reset_index()
    )
    stats["metrica"] = 100.0 * stats["convergentes"] / stats["n"]
    stats = stats.sort_values(["metrica", "codigo_ibge"], ascending=[False, True]).head(n)
    return [
        InsetSelecao(str(r.codigo_ibge), str(r.municipio), float(r.metrica))
        for r in stats.itertuples(index=False)
    ]


def categorizar_m08(base: pd.DataFrame) -> pd.Series:
    conv = pd.to_numeric(base["CONVERGENCIA_3_OU_4"], errors="coerce")
    n = pd.to_numeric(base["N_FAMILIAS_SINAL"], errors="coerce")
    out = pd.Series("0–2 dimensões", index=base.index, dtype="string")
    out.loc[conv.isna()] = "Classificação indeterminada"
    out.loc[conv.eq(1) & n.eq(3)] = "3 dimensões"
    out.loc[conv.eq(1) & n.eq(4)] = "4 dimensões"
    inesperado = conv.eq(1) & ~n.isin([3, 4])
    if inesperado.any():
        raise AssertionError(
            "Há convergência P75 incompatível com 3 ou 4 famílias sinalizadas."
        )
    return out


def categorizar_m09(base: pd.DataFrame) -> pd.Series:
    p75 = pd.to_numeric(base["CONVERGENCIA_3_OU_4"], errors="coerce")
    p80 = pd.to_numeric(base["CONVERGENCIA_3_OU_4_P80"], errors="coerce")
    persist = pd.to_numeric(base["PERSISTENTE_P75_P80"], errors="coerce")
    mesmo = pd.to_numeric(base["MESMO_VETOR_P75_P80"], errors="coerce")
    out = pd.Series("Fora do critério P75", index=base.index, dtype="string")
    out.loc[p75.isna()] = "P75 indeterminado"
    out.loc[p75.eq(1) & p80.eq(0)] = "P75, não persistente no P80"
    out.loc[p75.eq(1) & p80.isna()] = "P75, P80 indeterminado"
    out.loc[persist.eq(1) & mesmo.eq(0)] = "Persistente, composição alterada"
    out.loc[persist.eq(1) & mesmo.eq(1)] = "Persistente, mesmo vetor"
    return out


def preparar_m12(entorno: pd.DataFrame, esperado: int = 9087) -> pd.DataFrame:
    base = entorno.copy()
    base["codigo_setor"] = base["codigo_setor"].astype("string").str.strip()
    base["codigo_ibge"] = base["codigo_ibge"].astype("string").str.strip()
    if len(base) != esperado:
        raise AssertionError(f"M12 exige {esperado} setores urbanos; obtidos={len(base)}")
    if base["codigo_setor"].duplicated().any():
        raise AssertionError("M12 recebeu código de setor duplicado.")
    faltantes = [c for c in M12_COMPONENTES.values() if c not in base.columns]
    if faltantes:
        raise ValueError(f"M12 sem componentes obrigatórios: {faltantes}")
    for coluna in M12_COMPONENTES.values():
        base[coluna] = pd.to_numeric(base[coluna], errors="coerce")
    return base
