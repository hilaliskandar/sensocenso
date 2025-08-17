from __future__ import annotations
from typing import List, Tuple, Optional, Dict, Sequence
from functools import lru_cache
import os
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

def _norm_cd_mun(series: pd.Series) -> pd.Series:
    """Normaliza códigos de município para 7 dígitos (string de números)."""
    return pd.Series(series).astype(str).str.replace(r"\D", "", regex=True).str.zfill(7)

def _file_mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except Exception:
        return 0.0

@lru_cache(maxsize=8)
def _rm_au_lookup_from_excel_cached(excel_path: str, mtime: float) -> Tuple[Optional[Dict[str, str]], Optional[Dict[str, str]]]:
    """Carrega mapas RM/AU do Excel, cacheado por caminho+mtime.

    Retorna tupla (rm_map_dict, au_map_dict) mapeando CD_MUN -> nome.
    """
    try:
        xls = pd.ExcelFile(excel_path, engine="openpyxl")
    except Exception:
        return None, None

    def _exact_map(sheet_name: str, value_col_name: str) -> Optional[Dict[str, str]]:
        if sheet_name not in xls.sheet_names:
            return None
        try:
            tmp = pd.read_excel(xls, sheet_name=sheet_name)
        except Exception:
            return None
        cols = {str(c).strip(): c for c in tmp.columns}
        inv = { _normalize_simple(k).upper(): v for k, v in cols.items() }
        get = lambda k: inv.get(_normalize_simple(k).upper())
        cod = get("COD_MUN")
        nom = get("NOME_CATMETROPOL")
        uf  = get("SIGLA_UF")
        if not (cod and nom and uf):
            return None
        tmp = tmp[[cod, nom, uf]].copy()
        tmp = tmp[tmp[uf].astype(str).str.upper().eq("SP")]
        if tmp.empty:
            return None
        tmp["CD_MUN"] = _norm_cd_mun(tmp[cod])
        tmp = tmp[["CD_MUN", nom]].dropna().drop_duplicates()
        return dict(zip(tmp["CD_MUN"], tmp[nom]))

    rm_map = _exact_map("Composição - Recortes Metropoli", "RM_NOME")
    au_map = _exact_map("Composição - Aglomerações Urban", "AU_NOME")

    # Fallback heurístico se preciso
    if rm_map is None or au_map is None:
        try:
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
            rm_df = pd.read_excel(xls, sheet_name=rm_sheet)
            au_df = pd.read_excel(xls, sheet_name=au_sheet)
            # tentar detectar colunas
            def build_map(d: pd.DataFrame, name_candidates: List[str]) -> Optional[Dict[str, str]]:
                d = d.copy()
                d.columns = [_normcol(c) for c in d.columns]
                if "COD_MUN" not in d.columns:
                    # tenta CODIGO_DO_MUNICIPIO etc
                    for c in list(d.columns):
                        if c in {"CODIGO_DO_MUNICIPIO","COD_MUNICIPIO","CD_GEOCODM","CD_MUN","COD_MUN"}:
                            d.rename(columns={c: "COD_MUN"}, inplace=True)
                            break
                nom_col = next((c for c in name_candidates if c in d.columns), None)
                if "COD_MUN" not in d.columns or nom_col is None:
                    return None
                d["CD_MUN"] = _norm_cd_mun(d["COD_MUN"])
                d = d[["CD_MUN", nom_col]].dropna().drop_duplicates()
                return dict(zip(d["CD_MUN"], d[nom_col]))
            if rm_map is None:
                rm_map = build_map(rm_df, ["NOME_CATMETROPOL","RM_NOME","RM","NOME_RM"])
            if au_map is None:
                au_map = build_map(au_df, ["NOME_CATAU","AU_NOME","AU","NOME_AU"])
        except Exception:
            pass

    return rm_map, au_map

def enrich_with_municipality_lookup(df: pd.DataFrame, mapping: Dict[str, str], new_col: str,
                                    source_col: str = "CD_MUN", overwrite: bool = False) -> pd.DataFrame:
    """Enriquece df mapeando códigos de município para um novo rótulo.

    - mapping: dict CD_MUN (7 dígitos) -> valor
    - new_col: coluna a ser criada/preenchida
    - overwrite: se False (padrão), só preenche valores ausentes
    """
    if not mapping or source_col not in df.columns:
        return df
    out = df.copy()
    out[source_col] = _norm_cd_mun(out[source_col])
    mapped = out[source_col].map(mapping)
    if overwrite or new_col not in out.columns:
        out[new_col] = mapped
    else:
        out[new_col] = out[new_col].where(out[new_col].notna(), mapped)
    return out

def _merge_rm_au(df: pd.DataFrame, excel_path: str = "insumos/Composicao_RM_2024.xlsx") -> pd.DataFrame:
    """Enriquece o DataFrame com nomes de RM/AU com base no Excel fornecido.

    Regras prioritárias (exatas) conforme especificação:
    - Ler as abas:
        • "Composição - Aglomerações Urban" (AU)
        • "Composição - Recortes Metropoli" (RM)
    - Usar as colunas: COD_MUN, NOME_CATMETROPOL, SIGLA_UF
    - Filtrar apenas SIGLA_UF == "SP"
    - Produzir mapas: CD_MUN -> AU_NOME / RM_NOME

    Caso as abas/colunas exatas não existam, faz fallback heurístico anterior.
    Também cria coluna auxiliar REGIAO_RM_AU (prioriza RM, senão AU).
    """
    p = _P(excel_path)
    if not p.exists():
        return df
    out = df.copy()
    if "CD_MUN" not in out.columns:
        return out
    out["CD_MUN"] = _norm_cd_mun(out["CD_MUN"])

    rm_map, au_map = _rm_au_lookup_from_excel_cached(p.as_posix(), _file_mtime(p.as_posix()))
    if rm_map:
        out = enrich_with_municipality_lookup(out, rm_map, new_col="RM_NOME", source_col="CD_MUN", overwrite=False)
    if au_map:
        out = enrich_with_municipality_lookup(out, au_map, new_col="AU_NOME", source_col="CD_MUN", overwrite=False)

    if "REGIAO_RM_AU" not in out.columns:
        out["REGIAO_RM_AU"] = out.get("RM_NOME")
        if "AU_NOME" in out.columns:
            out["REGIAO_RM_AU"] = out["REGIAO_RM_AU"].where(out["REGIAO_RM_AU"].notna(), out["AU_NOME"])
    # Tipo da região (RM tem prioridade sobre AU)
    if "TIPO_RM_AU" not in out.columns:
        import pandas as _pd
        tipo = _pd.Series(_pd.NA, index=out.index, dtype="object")
        if "RM_NOME" in out.columns:
            tipo = tipo.where(~out["RM_NOME"].notna(), "RM")
        if "AU_NOME" in out.columns:
            tipo = tipo.where(~(tipo.isna() & out["AU_NOME"].notna()), "AU")
        out["TIPO_RM_AU"] = tipo
    # Alias opcional com nome mais explícito
    if "NOME_RM_AU" not in out.columns and "REGIAO_RM_AU" in out.columns:
        out["NOME_RM_AU"] = out["REGIAO_RM_AU"]
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

def _resolve_parquet_path(primary: Optional[str]) -> Tuple[str, List[str]]:
    """Resolve o caminho do parquet considerando múltiplas alternativas.

    Ordem de tentativa:
    1. Caminho informado (primary)
    2. Variável de ambiente SENSOCENSO_PARQUET
    3. Caminhos comuns no projeto (data/sp.parquet)
    4. Caminho absoluto indicado pelo usuário (D:\repo\saida_parquet\base_integrada_final.parquet)

    Retorna (caminho_resolvido_posix, lista_de_caminhos_testados)
    """
    tried: List[str] = []

    candidates: List[str] = []
    if primary:
        candidates.append(str(primary))
    envp = os.environ.get("SENSOCENSO_PARQUET")
    if envp:
        candidates.append(envp)
    # comuns relativos ao repo
    candidates.append("data/sp.parquet")
    # absoluto informado pelo usuário
    candidates.append(r"D:\\repo\\saida_parquet\\base_integrada_final.parquet")

    for c in candidates:
        if not c:
            continue
        tried.append(c)
        p = _P(c)
        if p.exists():
            return p.as_posix(), tried
    # não encontrado
    return "", tried

def load_sp_age_sex_enriched(path_parquet: str, limit: Optional[int] = None, verbose: bool = False, uf_code: str = "35", excel_path: Optional[str] = None) -> pd.DataFrame:
    if duckdb is None:
        raise ModuleNotFoundError("Instale 'duckdb' (pip install duckdb).")
    resolved, tried = _resolve_parquet_path(path_parquet)
    if not resolved:
        raise FileNotFoundError(
            "Parquet não encontrado. Caminhos testados: " + "; ".join(tried)
        )
    path_parquet = resolved
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
    geo_keys = [
        "CD_SETOR","CD_MUN","NM_MUN","CD_UF","NM_UF",
        "CD_SITUACAO","SITUACAO","SITUACAO_DET_TXT","CD_TIPO","TP_SETOR_TXT","V0001",
        "RM_NOME","AU_NOME","NM_RGINT","NM_RGI",
        "NOME_RM_AU","TIPO_RM_AU","REGIAO_RM_AU",
    ]
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

# --- Categóricos genéricos ---
from typing import Sequence as _Seq

def aggregate_categories(df: pd.DataFrame, columns: _Seq[str]) -> pd.DataFrame:
    """Soma colunas categóricas e retorna DataFrame com (categoria, valor).

    - Ignora colunas inexistentes silenciosamente.
    - Mantém apenas categorias com valor > 0 e não nulo.
    """
    cols = [c for c in columns if c in df.columns]
    if not cols:
        return pd.DataFrame({"categoria": [], "valor": []})
    sub = df[cols].copy()
    # Coagir cada coluna individualmente para numérico; valores não numéricos viram NaN
    for c in sub.columns:
        sub[c] = pd.to_numeric(sub[c], errors="coerce")
    # Somar por coluna para obter total por categoria
    vals = sub.sum(axis=0, skipna=True)
    out = pd.DataFrame({"categoria": vals.index, "valor": vals.values})
    out = out[out["valor"].notna() & (out["valor"] > 0)]
    return out.reset_index(drop=True)

def categories_to_percent(df_cat: pd.DataFrame) -> pd.DataFrame:
    """Converte valores para percentuais (0–100), preservando 'categoria' e colocando 'valor' como %.
    """
    if df_cat is None or df_cat.empty:
        return df_cat
    out = df_cat.copy()
    total = pd.to_numeric(out["valor"], errors="coerce").sum()
    if not total or total == 0:
        return out.assign(valor=0.0)
    out["valor"] = pd.to_numeric(out["valor"], errors="coerce").fillna(0) / float(total) * 100.0
    return out

def filter_by_situacao_tipo(df: pd.DataFrame, situacoes: _Seq[str] | None = None, tipos: _Seq[int] | None = None) -> pd.DataFrame:
    """Aplica filtros de situação (Urbana/Rural) e tipos de setor (CD_TIPO).
    Ignora filtros não informados ou colunas ausentes.
    """
    out = df.copy()
    if situacoes and "SITUACAO" in out.columns:
        out = out[out["SITUACAO"].isin(list(situacoes))]
    if tipos and "CD_TIPO" in out.columns:
        out = out[out["CD_TIPO"].isin(list(tipos))]
    return out

# Aliases PT-BR
def agregar_categorias(df: pd.DataFrame, colunas: _Seq[str]) -> pd.DataFrame:
    return aggregate_categories(df, columns=colunas)

def categorias_para_percentual(df_cat: pd.DataFrame) -> pd.DataFrame:
    return categories_to_percent(df_cat)

def filtrar_situacao_tipo(df: pd.DataFrame, situacoes: _Seq[str] | None = None, tipos: _Seq[int] | None = None) -> pd.DataFrame:
    return filter_by_situacao_tipo(df, situacoes, tipos)
