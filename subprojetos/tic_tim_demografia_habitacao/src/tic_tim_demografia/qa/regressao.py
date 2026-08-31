from __future__ import annotations

from pathlib import Path

import pandas as pd


CHAVE = ["codigo_ibge", "ano"]
COLUNAS_COMPARAR = [
    "pop_0_14",
    "pop_15_59",
    "pop_60_mais",
    "pop_total_harmonizada",
]


def carregar_oraculo_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"codigo_ibge": "string"})
    obrigatorias = CHAVE + COLUNAS_COMPARAR
    faltantes = [c for c in obrigatorias if c not in df.columns]
    if faltantes:
        raise ValueError(f"Oráculo de regressão sem colunas obrigatórias: {faltantes}")
    if df.duplicated(CHAVE).any():
        raise ValueError("Oráculo de regressão contém chaves duplicadas.")
    for c in COLUNAS_COMPARAR:
        df[c] = pd.to_numeric(df[c], errors="raise").astype("int64")
    df["ano"] = pd.to_numeric(df["ano"], errors="raise").astype(int)
    return df


def comparar_com_oraculo(
    produzido: pd.DataFrame,
    oraculo: pd.DataFrame,
    *,
    exigir_todas_chaves_oraculo: bool = True,
) -> dict:
    """Compara a base produzida com um oráculo pequeno e versionado de QA.

    O oráculo não participa do cálculo. Serve apenas como teste de regressão.
    Comparações são exatas para contagens censitárias inteiras.
    """
    prod = produzido.copy()
    prod["codigo_ibge"] = prod["codigo_ibge"].astype("string")
    prod["ano"] = pd.to_numeric(prod["ano"], errors="raise").astype(int)
    if prod.duplicated(CHAVE).any():
        raise ValueError("Base produzida contém chaves duplicadas antes do gate de regressão.")

    merged = oraculo.merge(
        prod[CHAVE + COLUNAS_COMPARAR],
        on=CHAVE,
        how="left",
        suffixes=("_ref", "_prod"),
        indicator=True,
    )
    ausentes = merged.loc[merged["_merge"] != "both", CHAVE].to_dict("records")
    if exigir_todas_chaves_oraculo and ausentes:
        raise AssertionError(f"Chaves do oráculo ausentes na base produzida: {ausentes}")

    divergencias: list[dict] = []
    for coluna in COLUNAS_COMPARAR:
        ref = f"{coluna}_ref"
        prod_col = f"{coluna}_prod"
        mask = merged["_merge"].eq("both") & merged[ref].ne(merged[prod_col])
        for _, linha in merged.loc[mask, CHAVE + [ref, prod_col]].iterrows():
            divergencias.append(
                {
                    "codigo_ibge": str(linha["codigo_ibge"]),
                    "ano": int(linha["ano"]),
                    "campo": coluna,
                    "referencia": int(linha[ref]),
                    "produzido": int(linha[prod_col]),
                    "diferenca": int(linha[prod_col] - linha[ref]),
                }
            )

    if divergencias:
        amostra = divergencias[:20]
        raise AssertionError(
            f"Gate de regressão reprovado: {len(divergencias)} divergências. Amostra={amostra}"
        )

    return {
        "status": "OK",
        "chaves_oraculo": int(len(oraculo)),
        "municipios_oraculo": int(oraculo["codigo_ibge"].nunique()),
        "anos_oraculo": sorted(int(x) for x in oraculo["ano"].unique()),
        "campos_comparados": list(COLUNAS_COMPARAR),
        "divergencias": 0,
    }
