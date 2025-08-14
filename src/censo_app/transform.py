from __future__ import annotations
from typing import List, Tuple, Optional, Dict
import re, unicodedata
import pandas as pd
from pathlib import Path as _P

try:
    import duckdb  # type: ignore
except Exception:
    duckdb = None  # type: ignore

SITUACAO_DET_MAP: Dict[int, str] = {
    1: "Área urbana de alta densidade de edificações de cidade ou vila",
    2: "Área urbana de baixa densidade de edificações de cidade ou vila",
    3: "Núcleo urbano",
    5: "Aglomerado rural - Povoado",
    6: "Aglomerado rural - Núcleo rural",
    7: "Aglomerado rural - Lugarejo",
    8: "Área rural (exclusive aglomerados)",
    9: "Massas de água",
}
TIPO_MAP: Dict[int, str] = {
    0: "Não especial",
    1: "Favela e Comunidade Urbana",
    2: "Quartel e base militar",
    3: "Alojamento / acampamento",
    4: "Setor com baixo patamar domiciliar",
    5: "Agrupamento indígena",
    6: "Unidade prisional",
    7: "Convento / hospital / ILPI / IACA",
    8: "Agrovila do PA",
    9: "Agrupamento quilombola",
}
AGE_GROUPS = [
    "0 a 4 anos","5 a 9 anos","10 a 14 anos","15 a 19 anos",
    "20 a 24 anos","25 a 29 anos","30 a 39 anos","40 a 49 anos",
    "50 a 59 anos","60 a 69 anos","70 anos ou mais",
]

def _normcol(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").upper()
    return s

ALIASES = {
    "CD_SETOR": {"CD_SETOR","GEOCODIGO_DE_SETOR_CENSITARIO","GEOCODIGO_SETOR_CENSITARIO"},
    "CD_MUN": {"CD_MUN","CODIGO_DO_MUNICIPIO","COD_MUN"},
    "NM_MUN": {"NM_MUN","NOME_DO_MUNICIPIO","NOME_MUNICIPIO"},
    "CD_UF": {"CD_UF","CODIGO_DA_UNIDADE_DA_FEDERACAO","UF_CODIGO"},
    "NM_UF": {"NM_UF","NOME_DA_UNIDADE_DA_FEDERACAO"},
    "CD_SITUACAO": {"CD_SITUACAO","SITUACAO_DETALHADA_DO_SETOR_CENSITARIO_CODIGO","COD_SITUACAO_DETALHADA"},
    "SITUACAO_DET_TXT": {"SITUACAO_DET_TXT","SITUACAO_DETALHADA_DO_SETOR_CENSITARIO"},
    "CD_TIPO": {"CD_TIPO","TIPO_DO_SETOR_CENSITARIO_CODIGO","COD_TIPO_SETOR"},
    "TP_SETOR_TXT": {"TP_SETOR_TXT","TIPO_DO_SETOR_CENSITARIO"},
    "SITUACAO": {"SITUACAO","SITUACAO_DO_SETOR_CENSITARIO","SIT_SETOR"},
}

def _rename_by_alias(df: pd.DataFrame) -> pd.DataFrame:
    rename = {}
    norm_lookup = {_normcol(c): c for c in df.columns}
    for canon, variants in ALIASES.items():
        for v in variants:
            if v in norm_lookup:
                rename[norm_lookup[v]] = canon
                break
    return df.rename(columns=rename)

def _derive_macro_from_cd(cd):
    try:
        c = int(str(cd))
    except Exception:
        return None
    return "Urbana" if c in (1,2,3) else "Rural"

def _normalize_codes(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for key in ("CD_SETOR","CD_MUN","CD_UF"):
        if key in out.columns:
            out[key] = out[key].astype(str).str.extract(r"(\d+)")[0].fillna(out[key].astype(str))
    return out

def _ensure_decodes(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "CD_SITUACAO" not in out.columns and "SITUACAO_DET_TXT" in out.columns:
        inv = {v:k for k,v in SITUACAO_DET_MAP.items()}
        out["CD_SITUACAO"] = out["SITUACAO_DET_TXT"].map(inv).astype("Int64")
    if "SITUACAO_DET_TXT" not in out.columns and "CD_SITUACAO" in out.columns:
        out["SITUACAO_DET_TXT"] = pd.to_numeric(out["CD_SITUACAO"], errors="coerce").map(SITUACAO_DET_MAP)
    if "CD_TIPO" not in out.columns and "TP_SETOR_TXT" in out.columns:
        invt = {v:k for k,v in TIPO_MAP.items()}
        out["CD_TIPO"] = out["TP_SETOR_TXT"].map(invt).astype("Int64")
    if "TP_SETOR_TXT" not in out.columns and "CD_TIPO" in out.columns:
        out["TP_SETOR_TXT"] = pd.to_numeric(out["CD_TIPO"], errors="coerce").map(TIPO_MAP)
    if "SITUACAO" not in out.columns:
        if "CD_SITUACAO" in out.columns:
            out["SITUACAO"] = out["CD_SITUACAO"].apply(_derive_macro_from_cd)
        elif "SITUACAO_DET_TXT" in out.columns:
            urb = {"Área urbana de alta densidade de edificações de cidade ou vila","Área urbana de baixa densidade de edificações de cidade ou vila","Núcleo urbano"}
            out["SITUACAO"] = out["SITUACAO_DET_TXT"].apply(lambda s: "Urbana" if s in urb else "Rural")
    return out

def _pick_exact_age_cols(columns: List[str]) -> Tuple[List[str], List[str]]:
    groups = AGE_GROUPS
    male_cols, female_cols = [], []
    for grp in groups:
        pat_m = re.compile(rf"^Sexo\s*masculino\s*,\s*{re.escape(grp)}\s*(?:_\d+)?$", re.IGNORECASE)
        pat_f = re.compile(rf"^Sexo\s*feminino\s*,\s*{re.escape(grp)}\s*(?:_\d+)?$", re.IGNORECASE)
        m_match = next((c for c in columns if pat_m.match(str(c).strip())), None)
        f_match = next((c for c in columns if pat_f.match(str(c).strip())), None)
        if m_match: male_cols.append(m_match)
        if f_match: female_cols.append(f_match)
    return male_cols, female_cols

def load_sp_age_sex_enriched(path_parquet: str, limit: Optional[int] = None, verbose: bool = False, uf_code: str = "35") -> pd.DataFrame:
    if duckdb is None:
        raise ModuleNotFoundError("Instale 'duckdb' (pip install duckdb).")
    p = _P(path_parquet)
    if not p.exists():
        raise FileNotFoundError(f"Parquet não encontrado: {p}")
    path_parquet = p.as_posix()
    con = duckdb.connect()
    cols_df = con.execute(f"SELECT * FROM read_parquet('{path_parquet}') LIMIT 0").fetchdf()
    cols = cols_df.columns.tolist()
    uf_candidates = [c for c in cols if re.fullmatch(r"(?i)(CD_UF|CODIGO_DA_UNIDADE_DA_FEDERACAO|UF_CODIGO)", str(c))]
    uf_col = uf_candidates[0] if uf_candidates else None
    sel_cols = [f'"{c}"' for c in cols]
    where = f'WHERE "{uf_col}" = \'{uf_code}\'' if uf_col else ""
    q = f"SELECT {', '.join(sel_cols)} FROM read_parquet('{path_parquet}') {where}"
    if limit:
        q += f" LIMIT {int(limit)}"
    df = con.execute(q).fetchdf()
    df = _rename_by_alias(df)
    df = _normalize_codes(df)
    df = _ensure_decodes(df)
    for v in [c for c in df.columns if c.startswith("V000")]:
        if v in ("V0005","V0006"):
            df[v] = pd.to_numeric(df[v], errors="coerce").astype("float64")
        else:
            df[v] = pd.to_numeric(df[v], errors="coerce")
    return df

def wide_to_long_pyramid(df_wide: pd.DataFrame) -> pd.DataFrame:
    if "SITUACAO" not in df_wide.columns and "CD_SITUACAO" in df_wide.columns:
        df_wide = df_wide.copy()
        df_wide["SITUACAO"] = df_wide["CD_SITUACAO"].apply(_derive_macro_from_cd)
    m_cols, f_cols = _pick_exact_age_cols(df_wide.columns.tolist())
    val_cols = m_cols + f_cols
    if not val_cols:
        raise ValueError("As colunas etárias esperadas (11 por sexo) não foram encontradas.")
    geo_keys = ["CD_SETOR","CD_MUN","NM_MUN","CD_UF","NM_UF","CD_SITUACAO","SITUACAO","SITUACAO_DET_TXT","CD_TIPO","TP_SETOR_TXT","V0001"]
    id_vars = [c for c in geo_keys if c in df_wide.columns]
    long = df_wide.melt(id_vars=id_vars, value_vars=val_cols, var_name="chave", value_name="valor")
    long["valor"] = pd.to_numeric(long["valor"], errors="coerce").fillna(0).astype("int64")
    def parse_key(k: str):
        s = str(k).strip()
        if s.lower().startswith("sexo masculino"):
            sexo = "Masculino"; idade = s.split(",",1)[1].strip()
        elif s.lower().startswith("sexo feminino"):
            sexo = "Feminino"; idade = s.split(",",1)[1].strip()
        else:
            sexo = "Total"; idade = s
        idade = re.sub(r"_\d+$","", idade).strip()
        return sexo, idade
    parsed = long["chave"].apply(parse_key)
    long["sexo"] = parsed.map(lambda t: t[0])
    long["idade_grupo"] = parsed.map(lambda t: t[1])
    long["idade_grupo"] = pd.Categorical(long["idade_grupo"], categories=AGE_GROUPS, ordered=True)
    return long
