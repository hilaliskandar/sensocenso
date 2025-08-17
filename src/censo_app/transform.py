from __future__ import annotations
from typing import List, Tuple, Optional, Dict, Sequence
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

# Rótulos oficiais para variáveis V0001–V0007
# Fonte: especificação fornecida pelo usuário
VAR_LABELS: Dict[str, str] = {
    "V0001": "Total de pessoas",
    "V0002": "Total de Domicílios (DPPO + DPPV + DPPUO + DPIO + DCCM + DCSM)",
    "V0003": "Total de Domicílios Particulares (DPPO + DPPV + DPPUO + DPIO)",
    "V0004": "Total de Domicílios Coletivos (DCCM + DCSM)",
    "V0005": "Média de moradores em Domicílios Particulares Ocupados (Total pessoas em Domicílios Particulares Ocupados / DPPO + DPIO)",
    "V0006": "Percentual de Domicílios Particulares Ocupados Imputados (Total DPO imputados / Total DPO)",
    "V0007": "Total de Domicílios Particulares Ocupados (DPPO + DPIO)",
}

# Cache do mapeamento externo gerado em docs/columns_map.csv
_COLMAP_CACHE: Optional[Dict[str, str]] = None

def _get_external_colmap(path: Optional[str] = None) -> Dict[str, str]:
    """Lê docs/columns_map.csv (se existir) e devolve um dicionário
    parquet_column -> app_equivalent (apenas quando diferente e não vazio).

    Resultado é cacheado para reduzir IO.
    """
    global _COLMAP_CACHE
    if _COLMAP_CACHE is not None:
        return _COLMAP_CACHE
    root = _P(__file__).resolve().parents[3]
    csv_path = _P(path) if path else (root / "docs" / "columns_map.csv")
    out: Dict[str, str] = {}
    try:
        if csv_path.exists():
            df_map = pd.read_csv(csv_path)
            if set(["parquet_column", "app_equivalent"]).issubset(df_map.columns):
                for row in df_map.itertuples(index=False):
                    orig = getattr(row, "parquet_column", None)
                    eqv = getattr(row, "app_equivalent", None)
                    if isinstance(orig, str) and isinstance(eqv, str) and orig and eqv and orig != eqv:
                        out[orig] = eqv
    except Exception:
        out = {}
    _COLMAP_CACHE = out
    return out

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
    "CD_SITUACAO": {"CD_SITUACAO","SITUACAO_DETALHADA_DO_SETOR_CENSITARIO_CODIGO","COD_SITUACAO_DETALHADA","Código da Situação detalhada do Setor Censitário"},
    "SITUACAO_DET_TXT": {"SITUACAO_DET_TXT","SITUACAO_DETALHADA_DO_SETOR_CENSITARIO","Situação detalhada do Setor Censitário"},
    "CD_TIPO": {"CD_TIPO","TIPO_DO_SETOR_CENSITARIO_CODIGO","COD_TIPO_SETOR"},
    "TP_SETOR_TXT": {"TP_SETOR_TXT","TIPO_DO_SETOR_CENSITARIO"},
    "SITUACAO": {"SITUACAO","SITUACAO_DO_SETOR_CENSITARIO","SIT_SETOR","Situação do Setor Censitário"},
    "RM_NOME": {"RM_NOME","NOME_CATMETROPOL","RM","NOME_RM"},
    "AU_NOME": {"AU_NOME","NOME_CATAU","NOME_CATÉU","AU","NOME_AU"},  # include accented É possibility (corrected encoding)
    "NM_RGINT": {"NM_RGINT","NOME_DA_REGIAO_GEOGRAFICA_INTERMEDIARIA"},
    "NM_RGI": {"NM_RGI","NOME_DA_REGIAO_GEOGRAFICA_IMEDIATA"},
}

def _rename_by_alias(df: pd.DataFrame) -> pd.DataFrame:
    # 0) Aplicar mapeamento externo (se disponível)
    ext = _get_external_colmap()
    if ext:
        df = df.rename(columns={c: ext[c] for c in df.columns if c in ext})

    rename = {}
    norm_lookup = {_normcol(c): c for c in df.columns}
    # 1) Aliases semânticos (campos de identificação/descrição)
    for canon, variants in ALIASES.items():
        for v in variants:
            nv = _normcol(v)
            if nv in norm_lookup:
                rename[norm_lookup[nv]] = canon
                break
    out = df.rename(columns=rename)
    # 2) Normalizar códigos v0001..v0007 para maiúsculo (V0001..V0007)
    extra = {}
    for c in out.columns:
        m = re.fullmatch(r"(?i)v000([1-7])", str(c).strip())
        if m:
            extra[c] = f"V000{m.group(1)}"
    if extra:
        out = out.rename(columns=extra)
    return out

def get_variable_label(code: str) -> Optional[str]:
    """Retorna o rótulo humano de uma variável V000x, se conhecido.

    Aceita maiúsculas/minúsculas (e.g., "v0005").
    """
    k = str(code).strip().upper()
    return VAR_LABELS.get(k)

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

def _normalize_simple(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s

def _merge_rm_au(df: pd.DataFrame, excel_path: str = "insumos/Composicao_RM_2024.xlsx") -> pd.DataFrame:
    p = _P(excel_path)
    if not p.exists():
        return df
    try:
        xls = pd.ExcelFile(p.as_posix(), engine="openpyxl")
    except Exception:
        return df
    # robust sheet detection
    norm = lambda s: _normalize_simple(s).lower()
    rm_sheet = None
    au_sheet = None
    for name in xls.sheet_names:
        n = norm(name)
        if "metrop" in n and ("composicao" in n or "composi" in n):
            rm_sheet = name
        if "aglomer" in n and ("urban" in n or "urbana" in n or "urbanas" in n):
            au_sheet = name
    rm_sheet = rm_sheet or "Composição - Recortes Metropoli"
    au_sheet = au_sheet or "Composição - Aglomerações Urban"
    try:
        rm = pd.read_excel(xls, sheet_name=rm_sheet)
        au = pd.read_excel(xls, sheet_name=au_sheet)
    except Exception:
        return df
    # normalize column names inside the Excel sheets
    rm = _rename_by_alias(rm)
    au = _rename_by_alias(au)
    # try common fallbacks
    # ensure COD_MUN exists; sometimes it's COD_MUN or COD_MUNICIPIO
    for d in (rm, au):
        if "COD_MUN" not in d.columns:
            for c in d.columns:
                if _normcol(c) in {"COD_MUN","CODIGO_DO_MUNICIPIO","COD_MUNICIPIO"}:
                    d.rename(columns={c:"COD_MUN"}, inplace=True)
                    break
        if "COD_MUN" in d.columns:
            d["COD_MUN"] = d["COD_MUN"].astype(str).str.extract(r"(\d+)")[0]
    out = df.copy()
    if "CD_MUN" in out.columns:
        out["CD_MUN"] = out["CD_MUN"].astype(str).str.extract(r"(\d+)")[0]
        if "COD_MUN" in rm.columns and ("NOME_CATMETROPOL" in rm.columns or "RM_NOME" in rm.columns):
            src = "NOME_CATMETROPOL" if "NOME_CATMETROPOL" in rm.columns else "RM_NOME"
            rm_map = rm[["COD_MUN", src]].dropna().drop_duplicates()
            rm_map.rename(columns={src:"RM_NOME"}, inplace=True)
            out = out.merge(rm_map, left_on="CD_MUN", right_on="COD_MUN", how="left")
            out.drop(columns=[c for c in ["COD_MUN"] if c in out.columns], inplace=True)
        if "COD_MUN" in au.columns and ("NOME_CATAU" in au.columns or "AU_NOME" in au.columns):
            srca = "NOME_CATAU" if "NOME_CATAU" in au.columns else "AU_NOME"
            au_map = au[["COD_MUN", srca]].dropna().drop_duplicates()
            au_map.rename(columns={srca:"AU_NOME"}, inplace=True)
            out = out.merge(au_map, left_on="CD_MUN", right_on="COD_MUN", how="left")
            out.drop(columns=[c for c in ["COD_MUN"] if c in out.columns], inplace=True)
    return out

def _pick_exact_age_cols(columns: List[str]) -> Tuple[List[str], List[str]]:
    male_cols, female_cols = [], []
    for grp in ["0 a 4 anos","5 a 9 anos","10 a 14 anos","15 a 19 anos","20 a 24 anos","25 a 29 anos","30 a 39 anos","40 a 49 anos","50 a 59 anos","60 a 69 anos","70 anos ou mais"]:
        pat_m = re.compile(rf"^Sexo\s*masculino\s*,\s*{re.escape(grp)}\s*(?:_\d+)?$", re.IGNORECASE)
        pat_f = re.compile(rf"^Sexo\s*feminino\s*,\s*{re.escape(grp)}\s*(?:_\d+)?$", re.IGNORECASE)
        m_match = next((c for c in columns if pat_m.match(str(c).strip())), None)
        f_match = next((c for c in columns if pat_f.match(str(c).strip())), None)
        if m_match: male_cols.append(m_match)
        if f_match: female_cols.append(f_match)
    return male_cols, female_cols

def load_sp_age_sex_enriched(path_parquet: str, limit: Optional[int] = None, verbose: bool = False, uf_code: str = "35", excel_path: Optional[str] = None) -> pd.DataFrame:
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
    if verbose:
        print(q)
    df = con.execute(q).fetchdf()
    df = _rename_by_alias(df)
    df = _normalize_codes(df)
    df = _ensure_decodes(df)
    for v in [c for c in df.columns if c.startswith("V000")]:
        if v in ("V0005","V0006"):
            df[v] = pd.to_numeric(df[v], errors="coerce").astype("float64")
        else:
            df[v] = pd.to_numeric(df[v], errors="coerce")
    df = _merge_rm_au(df, excel_path=excel_path or "insumos/Composicao_RM_2024.xlsx")
    return df

def wide_to_long_pyramid(df_wide: pd.DataFrame) -> pd.DataFrame:
    if "SITUACAO" not in df_wide.columns and "CD_SITUACAO" in df_wide.columns:
        df_wide = df_wide.copy()
        df_wide["SITUACAO"] = df_wide["CD_SITUACAO"].apply(_derive_macro_from_cd)
    m_cols, f_cols = _pick_exact_age_cols(df_wide.columns.tolist())
    val_cols = m_cols + f_cols
    if not val_cols:
        raise ValueError("As colunas etárias esperadas (11 por sexo) não foram encontradas.")
    geo_keys = ["CD_SETOR","CD_MUN","NM_MUN","CD_UF","NM_UF","CD_SITUACAO","SITUACAO","SITUACAO_DET_TXT","CD_TIPO","TP_SETOR_TXT","V0001","RM_NOME","AU_NOME","NM_RGINT","NM_RGI"]
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
    keep = [c for c in ["CD_SETOR","CD_MUN","NM_MUN","CD_UF","NM_UF","CD_SITUACAO","SITUACAO","SITUACAO_DET_TXT","CD_TIPO","TP_SETOR_TXT","V0001","RM_NOME","AU_NOME","NM_RGINT","NM_RGI","idade_grupo","sexo","valor"] if c in long.columns]
    return long[keep]

def aggregate_pyramid(df: pd.DataFrame, group_by: Sequence[str] | None = None) -> pd.DataFrame:
    group_by = list(group_by or [])
    need_long = not ({"idade_grupo","sexo","valor"} <= set(df.columns))
    df_long = wide_to_long_pyramid(df) if need_long else df.copy()
    if "idade_grupo" in df_long.columns:
        df_long["idade_grupo"] = pd.Categorical(df_long["idade_grupo"], categories=AGE_GROUPS, ordered=True)
    keys = [c for c in group_by if c in df_long.columns] + ["idade_grupo","sexo"]
    out = (df_long.groupby(keys, dropna=False, as_index=False)["valor"].sum()
                  .sort_values(keys)
                  .reset_index(drop=True))
    return out

# --- Aliases em PT-BR (não quebram compatibilidade) ---
def carregar_sp_idade_sexo_enriquecido(path_parquet: str, limite: Optional[int] = None, detalhar: bool = False, uf: str = "35", caminho_excel: Optional[str] = None) -> pd.DataFrame:
    return load_sp_age_sex_enriched(path_parquet, limit=limite, verbose=detalhar, uf_code=uf, excel_path=caminho_excel)

def largura_para_longo_piramide(df_largo: pd.DataFrame) -> pd.DataFrame:
    return wide_to_long_pyramid(df_largo)

def agregar_piramide(df: pd.DataFrame, agrupar_por: Sequence[str] | None = None) -> pd.DataFrame:
    return aggregate_pyramid(df, group_by=agrupar_por)
