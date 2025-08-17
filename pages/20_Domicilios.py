import streamlit as st
import pandas as pd
from pathlib import Path

from config.config_loader import get_settings
from censo_app.transform import carregar_sp_idade_sexo_enriquecido as carregar_base
from censo_app.viz import construir_grafico_pizza, construir_grafico_barra

st.set_page_config(page_title="Domicílios", layout="wide", initial_sidebar_state="collapsed")

SETTINGS = get_settings()

@st.cache_data(show_spinner=False)
def carregar_df():
    parquet = SETTINGS.get("paths", {}).get("parquet", "data/sp.parquet")
    excel_rm = SETTINGS.get("paths", {}).get("rm_xlsx", "insumos/Composicao_RM_2024.xlsx")
    df = carregar_base(parquet, limite=None, detalhar=False, uf="35", caminho_excel=excel_rm)
    return df

@st.cache_data(show_spinner=False)
def ler_grupos():
    import yaml
    p = Path("config/categorias.yaml")
    with p.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg.get("groups", [])

def _fmt_mun(cd: str|None, lookup: pd.DataFrame):
    if not cd:
        return "(selecione)"
    row = lookup.loc[lookup["CD_MUN"].astype(str)==str(cd)]
    if row.empty:
        return str(cd)
    return f"{row.iloc[0]['NM_MUN']} ({row.iloc[0]['CD_MUN']})"

df = carregar_df()
grupos = ler_grupos()

st.title("Domicílios — Indicadores Categóricos")

with st.sidebar:
    st.subheader("Filtros")
    sit_opts = sorted(df.get("SITUACAO", pd.Series(dtype=str)).dropna().unique().tolist()) or ["Urbana","Rural"]
    tipos = sorted(pd.to_numeric(df.get("CD_TIPO"), errors="coerce").dropna().unique().astype(int).tolist())
    sel_sit = st.multiselect("Situação", options=sit_opts, default=sit_opts)
    sel_tipos = st.multiselect("Tipo de Setor", options=tipos, default=tipos)
    nivel = st.selectbox("Nível", ["Estado","RM/AU","Região Intermediária","Região Imediata","Município","Setores"], index=4)

df_filt = df.copy()
if "SITUACAO" in df_filt.columns:
    df_filt = df_filt[df_filt["SITUACAO"].isin(sel_sit)]
if "CD_TIPO" in df_filt.columns and sel_tipos:
    df_filt = df_filt[df_filt["CD_TIPO"].isin(sel_tipos)]

# Escopo geográfico (mesma lógica da Demografia, versão compacta)
title_suffix = "Estado de São Paulo"
if nivel == "RM/AU" and "NOME_RM_AU" in df_filt.columns:
    nomes = sorted(df_filt["NOME_RM_AU"].dropna().unique().tolist())
    sel = st.selectbox("Região (RM/AU)", nomes)
    df_scope = df_filt[df_filt["NOME_RM_AU"].eq(sel)]
    title_suffix = sel
elif nivel == "Região Intermediária" and "NM_RGINT" in df_filt.columns:
    nomes = sorted(df_filt["NM_RGINT"].dropna().unique().tolist())
    sel = st.selectbox("Região Intermediária", nomes)
    df_scope = df_filt[df_filt["NM_RGINT"].eq(sel)]
    title_suffix = sel
elif nivel == "Região Imediata" and "NM_RGI" in df_filt.columns:
    nomes = sorted(df_filt["NM_RGI"].dropna().unique().tolist())
    sel = st.selectbox("Região Imediata", nomes)
    df_scope = df_filt[df_filt["NM_RGI"].eq(sel)]
    title_suffix = sel
elif nivel == "Município" and {"CD_MUN","NM_MUN"} <= set(df_filt.columns):
    mun_df = df_filt[["CD_MUN","NM_MUN"]].dropna().drop_duplicates()
    sel_mun = st.selectbox("Município", [None]+mun_df["CD_MUN"].tolist(), format_func=lambda x: _fmt_mun(x, mun_df))
    if sel_mun:
        df_scope = df_filt[df_filt["CD_MUN"].astype(str).eq(str(sel_mun))]
        title_suffix = _fmt_mun(sel_mun, mun_df)
    else:
        st.stop()
elif nivel == "Setores" and "CD_SETOR" in df_filt.columns:
    set_opts = sorted(df_filt["CD_SETOR"].dropna().unique().tolist())
    sel_set = st.selectbox("Setor", set_opts)
    df_scope = df_filt[df_filt["CD_SETOR"].eq(sel_set)]
    title_suffix = f"Setor {sel_set}"
else:
    df_scope = df_filt

# Comparador (opcional): mesmo recorte escolhido acima, comparado ao Estado em %
col_esq, col_dir = st.columns(2)
with col_esq:
    st.caption("Referência (Estado) em %")
with col_dir:
    st.caption("Selecionado (absoluto)")

for grupo in grupos:
    cols = [c for c in grupo.get("columns", []) if c in df_scope.columns]
    if not cols:
        continue
    titulo = grupo.get("title", "Indicador")
    chart = grupo.get("chart", "bar")
    # Agrega valores
    def _build(df_in: pd.DataFrame) -> pd.DataFrame:
        sub = df_in[cols].copy()
        vals = sub.sum(numeric_only=True)
        out = pd.DataFrame({"categoria": vals.index, "valor": vals.values})
        out = out[out["valor"].notna() & (out["valor"] > 0)]
        return out

    base_estado = _build(df_filt)  # estado após filtros
    base_sel = _build(df_scope)

    with st.container():
        st.subheader(titulo)
        c1, c2 = st.columns(2)
        with c1:
            if not base_estado.empty:
                if chart == "pie" and len(base_estado) <= 8:
                    st.plotly_chart(construir_grafico_pizza(base_estado, titulo=f"{titulo} — Estado (%)"), use_container_width=True)
                else:
                    st.plotly_chart(construir_grafico_barra(base_estado, titulo=f"{titulo} — Estado (%)"), use_container_width=True)
        with c2:
            if not base_sel.empty:
                if chart == "pie" and len(base_sel) <= 8:
                    st.plotly_chart(construir_grafico_pizza(base_sel, titulo=f"{titulo} — {title_suffix}"), use_container_width=True)
                else:
                    st.plotly_chart(construir_grafico_barra(base_sel, titulo=f"{titulo} — {title_suffix}"), use_container_width=True)

st.caption("Fonte: Censo 2022 — IBGE")
