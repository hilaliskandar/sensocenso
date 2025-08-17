from __future__ import annotations
import re
import pandas as pd
from typing import List


def normalize_age_label(lbl: str) -> str:
    """Normalize age bucket label into canonical form used in config.
    Examples:
      '30 a 34' -> '30 a 34 anos'
      '70+' or '70 ou mais' -> '70 anos ou mais'
      '0-4 anos' -> '0 a 4 anos'
    """
    try:
        s = str(lbl).strip().replace("–", "-").replace("—", "-")
        s = re.sub(r"\s*-\s*", " a ", s)
        m = re.search(r"(\d+)\s*a\s*(\d+)", s)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            return f"{a} a {b} anos"
        m = re.search(r"(\d+)\s*(\+|anos?\s*ou\s*mais|ou\s*mais)", s, re.IGNORECASE)
        if m:
            n = int(m.group(1))
            return f"{n} anos ou mais"
        m = re.search(r"(\d+)", s)
        if m:
            n = int(m.group(1))
            if n >= 70:
                return f"{n} anos ou mais"
        return s
    except Exception:
        return str(lbl)


def pad_pyramid_categories(df: pd.DataFrame, age_order: List[str]) -> pd.DataFrame:
    """Ensure both sexes have all age buckets present; fill missing with 0 and return aggregated df.
    Input columns: ['sexo','faixa_etaria','populacao']
    """
    sexes = ["Masculino", "Feminino"]
    base = pd.MultiIndex.from_product([sexes, age_order], names=["sexo","faixa_etaria"]).to_frame(index=False)
    df2 = df.copy()
    df2["faixa_etaria"] = df2["faixa_etaria"].apply(normalize_age_label)
    g = df2.groupby(["sexo","faixa_etaria"], as_index=False, observed=False)["populacao"].sum()
    out = base.merge(g, on=["sexo","faixa_etaria"], how="left")
    out["populacao"] = out["populacao"].fillna(0)
    return out


def aggregate_sex_age(df_long: pd.DataFrame) -> pd.DataFrame:
    return df_long.groupby(['sexo', 'faixa_etaria'], as_index=False, observed=False)['populacao'].sum()

# Aliases em PT-BR
def normalizar_rotulo_idade(rotulo: str) -> str:
    return normalize_age_label(rotulo)

def preencher_categorias_piramide(df: pd.DataFrame, ordem_idades: List[str]) -> pd.DataFrame:
    return pad_pyramid_categories(df, ordem_idades)

def agregar_sexo_idade(df_longo: pd.DataFrame) -> pd.DataFrame:
    return aggregate_sex_age(df_longo)
