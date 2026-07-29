"""Página de Indicadores Demográficos.

Calcula e exibe razões de dependência, índices de envelhecimento e outros
indicadores demográficos por município, setor, RM/AU ou escopo regional,
usando o mesmo dataset do Censo 2022 (SP) carregado na sessão.
"""
import sys
from pathlib import Path as _P
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

ROOT = _P(__file__).resolve().parents[1]
SRC = ROOT / "src"
for _pth in (str(SRC), str(ROOT)):
    if _pth not in sys.path:
        sys.path.insert(0, _pth)

from censo_app.ui import render_topbar
from censo_app.transform import carregar_sp_idade_sexo_enriquecido
from censo_app.formatting import fmt_br as _fmt_br
from censo_app.text_utils import sanitize_title as _sanitize_title
from censo_app.indicadores_demograficos import (
    calcular_age_heaping_index,
    calcular_indicadores_demograficos,
    calcular_populacoes_agrupadas,
    gerar_flags_qualidade,
)
from config.config_loader import get_settings

st.set_page_config(page_title="Indicadores Demográficos", layout="wide", initial_sidebar_state="collapsed")
render_topbar(title="Explorador de Dados Censitários", subtitle="Censo 2022 — SP")
st.title("📊 Indicadores Demográficos")

# ---------------------------------------------------------------------------
# CSS compacto
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .block-container { padding-left: 0.75rem !important; padding-right: 0.75rem !important; max-width: 100% !important; }
    .block-container h1,.block-container h2,.block-container h3,.block-container h4 {
        white-space: normal !important; overflow-wrap: anywhere; word-break: break-word;
    }
    table.ind-table { border-collapse: collapse; width: 100%; border-top: 2px solid #000;
        border-bottom: 2px solid #000; font-family: Arial, serif; font-size: 13px; }
    table.ind-table th, table.ind-table td { padding: 6px 12px; text-align: right;
        border-left: none; border-right: none; }
    table.ind-table th:first-child, table.ind-table td:first-child { text-align: left; }
    table.ind-table thead th { border-bottom: 1px solid #000; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Carregamento de dados (reutiliza sessão da Demografia se possível)
# ---------------------------------------------------------------------------
settings = get_settings()
parquet_path = (settings.get("paths", {}).get("parquet_default", "data/censo2022_sp.parquet")).strip().strip('"').strip("'").replace("\\", "/")
rm_xlsx_path = (settings.get("paths", {}).get("rm_au_excel_default", "insumos/Composicao_RM_2024.xlsx")).strip().strip('"').strip("'").replace("\\", "/")


@st.cache_data(show_spinner=True, ttl=3600)
def _load_wide(parquet: str, excel: str) -> pd.DataFrame:
    return carregar_sp_idade_sexo_enriquecido(parquet, limite=None, detalhar=False, uf="35", caminho_excel=excel)


if "df_wide_demog" in st.session_state:
    df_wide = st.session_state["df_wide_demog"]
else:
    try:
        with st.spinner("Carregando dados…"):
            df_wide = _load_wide(parquet_path, rm_xlsx_path)
        st.session_state["df_wide_demog"] = df_wide
    except Exception as exc:
        st.error(f"❌ Erro ao carregar dados: {exc}")
        st.info("Configure os caminhos em `config/settings.yaml` e reinicie o app.")
        st.stop()

# ---------------------------------------------------------------------------
# Converte wide → long com idade SIMPLES (ano a ano) para indicadores
# Usa as colunas de faixas etárias (11 grupos) mapeando para valor médio da faixa
# ---------------------------------------------------------------------------
AGE_MIDPOINTS = {
    "0 a 4 anos": 2,
    "5 a 9 anos": 7,
    "10 a 14 anos": 12,
    "15 a 19 anos": 17,
    "20 a 24 anos": 22,
    "25 a 29 anos": 27,
    "30 a 39 anos": 34,
    "40 a 49 anos": 44,
    "50 a 59 anos": 54,
    "60 a 69 anos": 64,
    "70 anos ou mais": 75,
}


def _build_long_for_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Converte wide → long com ponto médio de idade para uso nos indicadores."""
    import re
    male_pat = re.compile(r"^Sexo\s*masculino\s*,\s*(.+?)(?:\s*_\d+)?$", re.IGNORECASE)
    female_pat = re.compile(r"^Sexo\s*feminino\s*,\s*(.+?)(?:\s*_\d+)?$", re.IGNORECASE)
    rows = []
    geo_cols = [c for c in ["CD_SETOR", "CD_MUN", "NM_MUN", "SITUACAO", "CD_TIPO",
                             "RM_NOME", "AU_NOME", "NOME_RM_AU", "NM_RGI", "NM_RGINT"] if c in df.columns]
    for col in df.columns:
        m_m = male_pat.match(str(col).strip())
        m_f = female_pat.match(str(col).strip())
        for match, sexo in [(m_m, "Masculino"), (m_f, "Feminino")]:
            if match:
                grp_raw = match.group(1).strip()
                grp_raw = re.sub(r"_\d+$", "", grp_raw).strip()
                idade_mid = AGE_MIDPOINTS.get(grp_raw)
                if idade_mid is None:
                    continue
                tmp = df[geo_cols + [col]].copy()
                tmp = tmp.rename(columns={col: "pop"})
                tmp["sexo"] = sexo
                tmp["idade"] = idade_mid
                tmp["faixa"] = grp_raw
                tmp["pop"] = pd.to_numeric(tmp["pop"], errors="coerce").fillna(0)
                rows.append(tmp)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


@st.cache_data(show_spinner=False)
def _build_indicators_long(df_wide_id: int) -> pd.DataFrame:
    return _build_long_for_indicators(df_wide)


# Use hash of shape as a cheap cache key
_df_long_ind = _build_long_for_indicators(df_wide)

if _df_long_ind.empty:
    st.error("❌ Não foi possível converter os dados para o formato de indicadores. "
             "Verifique se o Parquet contém as colunas etárias esperadas.")
    st.stop()

# ---------------------------------------------------------------------------
# Filtros sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.subheader("Filtros")
    sit_opts = sorted(s for s in _df_long_ind.get("SITUACAO", pd.Series(dtype=str)).dropna().unique() if s in ("Urbana", "Rural"))
    sel_sit = st.multiselect("Situação", sit_opts, default=sit_opts or ["Urbana"])

st.divider()
st.subheader("🔍 Escopo de Análise")

# Escala
scale_opts = ["Estado"]
if "NOME_RM_AU" in _df_long_ind.columns or any(c in _df_long_ind.columns for c in ["RM_NOME", "AU_NOME"]):
    scale_opts.append("RM/AU")
if "NM_RGINT" in _df_long_ind.columns:
    scale_opts.append("Região Intermediária")
if "NM_RGI" in _df_long_ind.columns:
    scale_opts.append("Região Imediata")
if "CD_MUN" in _df_long_ind.columns:
    scale_opts.append("Município")

nivel = st.selectbox("Escala de Análise", scale_opts, key="nivel_ind")

# Aplica filtro de situação
df_filt = _df_long_ind.copy()
if sel_sit and "SITUACAO" in df_filt.columns:
    df_filt = df_filt[df_filt["SITUACAO"].isin(sel_sit)]

# Recorte geográfico
title_suffix = "Estado de São Paulo"
if nivel == "RM/AU":
    if "NOME_RM_AU" in df_filt.columns:
        opts = sorted(df_filt["NOME_RM_AU"].dropna().unique())
        sel = st.selectbox("RM/AU", opts, key="ind_rmau")
        df_filt = df_filt[df_filt["NOME_RM_AU"] == sel]
        title_suffix = sel
    else:
        st.warning("Colunas RM/AU não disponíveis nos dados.")
elif nivel == "Região Intermediária" and "NM_RGINT" in df_filt.columns:
    opts = sorted(df_filt["NM_RGINT"].dropna().unique())
    sel = st.selectbox("Região Intermediária", opts, key="ind_rgint")
    df_filt = df_filt[df_filt["NM_RGINT"] == sel]
    title_suffix = f"Região Intermediária — {sel}"
elif nivel == "Região Imediata" and "NM_RGI" in df_filt.columns:
    opts = sorted(df_filt["NM_RGI"].dropna().unique())
    sel = st.selectbox("Região Imediata", opts, key="ind_rgi")
    df_filt = df_filt[df_filt["NM_RGI"] == sel]
    title_suffix = f"Região Imediata — {sel}"
elif nivel == "Município" and "CD_MUN" in df_filt.columns:
    mun_df = df_filt[["CD_MUN", "NM_MUN"]].dropna().drop_duplicates().sort_values("NM_MUN") if "NM_MUN" in df_filt.columns else df_filt[["CD_MUN"]].drop_duplicates()
    name_map = dict(zip(mun_df["CD_MUN"], mun_df.get("NM_MUN", mun_df["CD_MUN"])))
    sel_mun = st.selectbox("Município", [None] + mun_df["CD_MUN"].tolist(),
                           format_func=lambda x: "(selecione)" if x is None else f"{x} — {name_map.get(x, '')}",
                           key="ind_mun")
    if sel_mun is None:
        st.info("Selecione um município para calcular os indicadores.")
        st.stop()
    df_filt = df_filt[df_filt["CD_MUN"] == sel_mun]
    title_suffix = f"{name_map.get(sel_mun, sel_mun)} ({sel_mun})"

if df_filt.empty:
    st.warning("⚠️ Nenhum dado disponível para os filtros selecionados.")
    st.stop()

# ---------------------------------------------------------------------------
# Cálculo dos indicadores
# ---------------------------------------------------------------------------
grupos = calcular_populacoes_agrupadas(df_filt, idade_col="idade", sexo_col="sexo", pop_col="pop")
indicadores = calcular_indicadores_demograficos(grupos)
whipple = calcular_age_heaping_index(df_filt, idade_col="idade", pop_col="pop")
indicadores["whipple_index"] = whipple
flags = gerar_flags_qualidade(grupos, whipple_index=whipple)

st.divider()
st.subheader(f"📈 Indicadores — {_sanitize_title(title_suffix)}")

# ---------------------------------------------------------------------------
# Métricas em cards
# ---------------------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)

pop_total = int(grupos.get("pop_total", 0))
pop_0_14 = int(grupos.get("pop_0_14", 0))
pop_65p = int(grupos.get("pop_65p", 0))
pop_15_64 = int(grupos.get("pop_15_64", 0))

col1.metric("👥 População Total", _fmt_br(pop_total))
col2.metric("👶 Pop. 0–14 anos", _fmt_br(pop_0_14),
            f"{_fmt_br(pop_0_14 / pop_total * 100, 1)}%" if pop_total else None)
col3.metric("🧑 Pop. 15–64 anos", _fmt_br(pop_15_64),
            f"{_fmt_br(pop_15_64 / pop_total * 100, 1)}%" if pop_total else None)
col4.metric("👴 Pop. 65+ anos", _fmt_br(pop_65p),
            f"{_fmt_br(pop_65p / pop_total * 100, 1)}%" if pop_total else None)

st.markdown("---")

# ---------------------------------------------------------------------------
# Tabela de indicadores (padrão ABNT)
# ---------------------------------------------------------------------------
INDICADORES_DEF = [
    ("RDT",   "Razão de Dependência Total",        "RDT = (P₀₋₁₄ + P₆₅₊) / P₁₅₋₆₄ × 100",    "%"),
    ("RDJ",   "Razão de Dependência Jovem",         "RDJ = P₀₋₁₄ / P₁₅₋₆₄ × 100",              "%"),
    ("RDI",   "Razão de Dependência de Idosos",     "RDI = P₆₅₊ / P₁₅₋₆₄ × 100",               "%"),
    ("OADR",  "Old Age Dependency Ratio",            "OADR = P₆₅₊ / P₂₀₋₆₄ × 100",              "%"),
    ("PSR",   "Potential Support Ratio",             "PSR = P₂₀₋₆₄ / P₆₅₊",                     "pessoas/idoso"),
    ("IE_60p","Índice de Envelhecimento (60+)",      "IE₆₀ = P₆₀₊ / P₀₋₁₄ × 100",               "%"),
    ("IE_65p","Índice de Envelhecimento (65+)",      "IE₆₅ = P₆₅₊ / P₀₋₁₄ × 100",               "%"),
    ("Prop_80p","Proporção de 80+ anos",             "P₈₀₊ / P_total × 100",                     "%"),
    ("TBN_proxy","Taxa Bruta de Natalidade (proxy)", "P₀ / P_total × 1000",                      "‰"),
]

rows_tab = []
for key, nome, formula, unidade in INDICADORES_DEF:
    val = indicadores.get(key, float("nan"))
    if pd.isna(val):
        val_str = "—"
    elif unidade == "pessoas/idoso":
        val_str = _fmt_br(val, 1)
    else:
        val_str = _fmt_br(val, 1)
    rows_tab.append({"Indicador": nome, "Símbolo": key, "Valor": val_str, "Unidade": unidade, "Fórmula": formula})

df_tab = pd.DataFrame(rows_tab)

def _render_ind_table(df: pd.DataFrame) -> str:
    thead = "<tr>" + "".join(f"<th>{c}</th>" for c in df.columns) + "</tr>"
    rows_html = []
    for _, r in df.iterrows():
        tds = "".join(f"<td>{r[c]}</td>" for c in df.columns)
        rows_html.append(f"<tr>{tds}</tr>")
    return (
        "<table class='ind-table'>"
        f"<thead>{thead}</thead>"
        f"<tbody>{''.join(rows_html)}</tbody>"
        "</table>"
    )

st.markdown(
    f"<div style='text-align:center;font-weight:bold;font-size:11pt;margin-bottom:4px;'>"
    f"Tabela 1 — Indicadores demográficos — {_sanitize_title(title_suffix)}"
    f"</div>",
    unsafe_allow_html=True,
)
st.markdown(_render_ind_table(df_tab), unsafe_allow_html=True)
st.markdown(
    "<div style='font-size:10pt;'>Fonte: Elaboração própria com dados do Censo Demográfico 2022 (IBGE). "
    "*TBN proxy: crianças de 0 anos / população total × 1000; não representa taxa de natalidade calculada pelo método demográfico padrão.</div>",
    unsafe_allow_html=True,
)

# Download
csv_ind = df_tab.to_csv(index=False, encoding="utf-8-sig")
st.download_button("📥 Baixar Indicadores (CSV)", csv_ind,
                   file_name=f"indicadores_{_sanitize_title(title_suffix).replace(' ', '_')}.csv",
                   mime="text/csv")

# ---------------------------------------------------------------------------
# Flags de qualidade
# ---------------------------------------------------------------------------
st.divider()
st.subheader("🔍 Flags de Qualidade")

flag_defs = {
    "denominador_pequeno": ("⚠️ Denominador pequeno",
                            "Pop. 15–64 < 500: razões de dependência podem ser instáveis."),
    "zero_total":          ("🚫 Sem população",
                            "Total de pessoas = 0: verifique filtros e dados."),
    "idosos_dominantes":   ("📈 Idosos dominantes",
                            "Pop. 65+ > Pop. 0–14: município com envelhecimento avançado."),
    "alta_prop_80p":       ("📊 Alta proporção 80+",
                            "Mais de 5% da população tem 80 anos ou mais."),
    "age_heaping":         ("🔴 Age Heaping severo",
                            f"Índice de Whipple = {_fmt_br(whipple, 1)} (> 174): qualidade dos dados de idade ruim."),
    "age_heaping_moderado":("🟡 Age Heaping moderado",
                            f"Índice de Whipple = {_fmt_br(whipple, 1)} (105–174): qualidade moderada."),
    "tbn_proxy_suspeita":  ("⚠️ TBN proxy suspeita",
                            "Proxy de natalidade < 5‰ ou > 35‰: verificar completude dos dados para idade 0."),
}

active_flags = {k: v for k, v in flag_defs.items() if flags.get(k)}
if active_flags:
    for flag_key, (label, desc) in active_flags.items():
        st.warning(f"**{label}** — {desc}")
else:
    st.success("✅ Nenhuma flag de qualidade ativa para este recorte.")

with st.expander("ℹ️ Sobre os indicadores e flags"):
    st.markdown("""
**Razões de dependência** medem a proporção da população dependente (jovens e idosos)
em relação à população em idade ativa (15–64). Valores altos indicam maior pressão
sobre a população produtiva.

**Índice de Envelhecimento** compara o tamanho da população idosa com a infantil.
Valores acima de 100% indicam que há mais idosos do que crianças.

**OADR** (Old Age Dependency Ratio) e **PSR** (Potential Support Ratio) são indicadores
complementares usados em análises previdenciárias.

**Índice de Whipple**: mede age heaping (preferência por idades terminadas em 0 ou 5).
- < 105: dados de alta qualidade
- 105–174: dados de qualidade moderada
- > 174: dados de qualidade ruim

**TBN proxy**: utiliza a contagem de crianças de 0 anos como indicativo de nascimentos recentes.
Não é equivalente à taxa de natalidade calculada por método demográfico padrão.
""")

# ---------------------------------------------------------------------------
# Gráfico: distribuição etária por faixa
# ---------------------------------------------------------------------------
st.divider()
st.subheader("📉 Distribuição Etária por Faixa")

if "faixa" in df_filt.columns:
    ORDER = list(AGE_MIDPOINTS.keys())
    df_faixa = (
        df_filt.groupby("faixa", as_index=False)["pop"].sum()
        .assign(ordem=lambda d: d["faixa"].apply(lambda x: ORDER.index(x) if x in ORDER else 99))
        .sort_values("ordem")
    )
    fig = go.Figure()
    fig.add_bar(x=df_faixa["faixa"], y=df_faixa["pop"], name="População",
                marker_color="#1f77b4")
    fig.update_layout(
        xaxis_title="Faixa Etária",
        yaxis_title="População",
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=60),
        xaxis_tickangle=-30,
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Fonte: Elaboração própria com dados do Censo Demográfico 2022 (IBGE).")

st.divider()
st.caption("Fonte: Censo 2022 — IBGE · Página: https://www.ibge.gov.br/")
