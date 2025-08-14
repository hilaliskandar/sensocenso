
from __future__ import annotations
import requests
import pandas as pd
from typing import Literal

SIDRA_BASE = "https://api.sidra.ibge.gov.br/values"

def fetch_sidra_table(
    table_id: int,
    periodo: str = "2022",
    nivel: Literal["BR","UF","MU"] = "BR",
    local: str = "1",
    variavel: str = "93",
    classificacao: str | None = None,
    categorias: str | None = None,
) -> pd.DataFrame:
    nivel_map = {"BR":"n1","UF":"n2","MU":"n6"}
    n = nivel_map[nivel]
    path = f"/t/{table_id}/p/{periodo}/v/{variavel}"
    if classificacao and categorias:
        path += f"/c{classificacao}/{categorias}"
    path += f"/{n}/{local}?formato=json"
    url = SIDRA_BASE + path
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    data = r.json()
    rows = data[1:]
    df = pd.DataFrame(rows)
    colmap = {}
    for c in df.columns:
        if c == "D2N": colmap[c] = "sexo"
        if c == "D3N": colmap[c] = "idade_grupo"
        if c == "D4N": colmap[c] = "idade_grupo"
        if c == "V":   colmap[c] = "valor"
        if c == "D1C": colmap[c] = "cod"
        if c == "D1N": colmap[c] = "nome"
    df = df.rename(columns=colmap)
    if "valor" in df.columns:
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    return df

def get_age_sex_groups(
    table_id: int = 1209,
    periodo: str = "2022",
    nivel: Literal["BR","UF","MU"] = "BR",
    local: str = "all",
) -> pd.DataFrame:
    try:
        df = fetch_sidra_table(table_id, periodo, nivel, local, variavel="93", classificacao="2", categorias="all")
        if "sexo" in df.columns and ("idade_grupo" in df.columns or "D3N" in df.columns or "D4N" in df.columns):
            return df
    except Exception:
        pass
    df = fetch_sidra_table(table_id, periodo, nivel, local, variavel="93")
    df["sexo"] = "Total"
    if "D2N" in df.columns and "idade_grupo" not in df.columns:
        df = df.rename(columns={"D2N":"idade_grupo"})
    return df
