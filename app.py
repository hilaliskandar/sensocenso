
import sys
from pathlib import Path as _P
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

SRC = _P(__file__).resolve().parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from censo_app.transform import (
    load_sp_age_sex_enriched, aggregate_pyramid, SITUACAO_DET_MAP, TIPO_MAP
)
from censo_app.viz import make_age_pyramid
from censo_app.ui import render_topbar
from config.config_loader import cfg

st.set_page_config(page_title="Explorador de Dados Censitários", layout="wide")

render_topbar(title="Explorador de Dados Censitários", subtitle="Censo 2022 — SP")

# CSS: destacar áreas selecionáveis como "botões" e permitir quebra de linha em títulos/labels
st.markdown(
    """
    <style>
    /* Selects e multiselects com fundo/contorno para parecer botão */
    div[data-baseweb="select"] > div {
        background-color: #f0f7ff !important;
        border: 1px solid #1f6feb !important;
        border-radius: 8px !important;
        transition: box-shadow .2s ease-in-out;
    }
    div[data-baseweb="select"] > div:hover {
        box-shadow: 0 0 0 3px rgba(31,110,235,0.18) !important;
    }
    /* Quebra de linha em labels e valores do select */
    .stSelectbox label, .stMultiSelect label { white-space: normal !important; }
    div[data-baseweb="select"] [role="combobox"] { white-space: normal !important; }
    div[data-baseweb="select"] span { white-space: normal !important; }
    /* Permitir quebra de linha em títulos/subtítulos */
    .block-container h1, .block-container h2, .block-container h3, .block-container h4 { 
        white-space: normal !important; 
        overflow-wrap: anywhere; 
        word-break: break-word; 
    }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    keepalive = st.checkbox("Evitar expirar (autorefresh a cada 5 min)", value=False)
    if keepalive and st_autorefresh:
        st_autorefresh(interval=5*60*1000, key="keepalive")
    elif keepalive:
        st.info("Para ativar: pip install streamlit-autorefresh")

    # Navegação explícita para garantir acesso às páginas (além da navegação padrão do Streamlit)
    st.markdown("---")
    st.caption("Navegação")
    try:
        st.page_link("app.py", label="Início", icon="🏠")
        st.page_link("pages/10_Demografia.py", label="Demografia", icon="🏛️")
        st.page_link("pages/10_SensoCenso_Explorador.py", label="Explorador", icon="🧭")
        st.page_link("pages/99_Sobre.py", label="Sobre", icon="ℹ️")
    except Exception:
        # Se a API não existir nesta versão do Streamlit, apenas ignora
        pass

def _norm(s: str) -> str:
    return (s or "").strip().strip('"').strip("'").replace("\\", "/")

# Carrega caminhos de settings.yaml (quando disponível) com fallback seguro
path_default = r"D:\\repo\\saida_parquet\\base_integrada_final.parquet"
excel_default = "insumos/Composicao_RM_2024.xlsx"
parquet_path = _norm(cfg("paths.parquet_default", path_default))
excel_path = _norm(cfg("paths.rm_au_excel_default", excel_default))

@st.cache_data(show_spinner=True, ttl=3600)
def _load(path: str, excel: str) -> pd.DataFrame:
    return load_sp_age_sex_enriched(path, limit=None, verbose=False, uf_code="35", excel_path=excel)

df = None
if hasattr(st, "status"):
    with st.status("Carregando dados…", expanded=True) as st_status:
        prog = st.progress(0, text="Preparando…")
        prog.progress(10, text="Validando caminhos…")
        ok_parquet = os.path.exists(parquet_path)
        ok_excel = os.path.exists(excel_path)
        prog.progress(30, text="Inicializando leitura…")
        try:
            with st.spinner("Lendo Parquet e enriquecendo RM/AU…"):
                df = _load(parquet_path, excel_path)
            prog.progress(90, text="Finalizando…")
            st_status.update(label="Dados carregados com sucesso", state="complete")
            prog.progress(100)
            st.caption(f"Base carregada (SP): {len(df):,} linhas.")
        except Exception as e:
            st_status.update(label=f"Erro ao carregar dados: {e}", state="error")
            st.error(f"Falha ao ler Parquet: {e}")
            st.stop()
else:
    try:
        with st.spinner("Carregando dados…"):
            df = _load(parquet_path, excel_path)
        st.caption(f"Base carregada (SP): {len(df):,} linhas.")
    except Exception as e:
        st.error(f"Falha ao ler Parquet: {e}")
        st.stop()

# (sem diagnósticos verbosos na UI principal)

with st.expander("Filtros", expanded=True):
    c1,c2,c3 = st.columns(3)
    if "SITUACAO" in df.columns:
        macro_opts = sorted([x for x in df["SITUACAO"].dropna().unique().tolist() if x in ("Urbana","Rural")]) or ["Urbana","Rural"]
        sel_macro = c1.multiselect("Situação (Urbana/Rural)", macro_opts, default=st.session_state.get("sel_macro", macro_opts), key="sel_macro")
        if sel_macro: df = df[df["SITUACAO"].isin(sel_macro)]
    if "CD_SITUACAO" in df.columns or "SITUACAO_DET_TXT" in df.columns:
        items = list(SITUACAO_DET_MAP.items())
        default_sit = st.session_state.get("sel_sit", items)
        sel_sit = c2.multiselect("Situação detalhada do Setor Censitário (decodificada)", items, default=default_sit, format_func=lambda t: f"{t[0]} — {t[1]}", key="sel_sit")
        if sel_sit:
            sel_codes = [k for k,_ in sel_sit]
            if "CD_SITUACAO" in df.columns:
                df = df[df["CD_SITUACAO"].isin(sel_codes)]
            else:
                inv = {v:k for k,v in SITUACAO_DET_MAP.items()}
                df = df[df["SITUACAO_DET_TXT"].map(inv).isin(sel_codes)]
    if "CD_TIPO" in df.columns or "TP_SETOR_TXT" in df.columns:
        tipo_items = list(TIPO_MAP.items())
        default_tipo = st.session_state.get("sel_tipo", tipo_items)
        sel_tipo = c3.multiselect("Tipo do Setor Censitário (decodificado)", tipo_items, default=default_tipo, format_func=lambda t: f"{t[0]} — {t[1]}", key="sel_tipo")
        if sel_tipo:
            sel_codes_t = [k for k,_ in sel_tipo]
            if "CD_TIPO" in df.columns:
                df = df[df["CD_TIPO"].isin(sel_codes_t)]
            else:
                invt = {v:k for k,v in TIPO_MAP.items()}
                df = df[df["TP_SETOR_TXT"].map(invt).isin(sel_codes_t)]

def _mk_municipios(df: pd.DataFrame) -> pd.DataFrame:
    return df[["CD_MUN","NM_MUN"]].dropna().drop_duplicates().sort_values(["NM_MUN","CD_MUN"]) if set(["CD_MUN","NM_MUN"]).issubset(df.columns) else pd.DataFrame(columns=["CD_MUN","NM_MUN"])    

def _mk_rm_au_options(df: pd.DataFrame) -> pd.DataFrame:
    # Produz lista única combinando RM e AU em um único seletor (mutuamente exclusivos)
    if {"TIPO_RM_AU","NOME_RM_AU"}.issubset(df.columns):
        out = (
            df[["TIPO_RM_AU","NOME_RM_AU"]]
            .dropna()
            .drop_duplicates()
            .sort_values(["TIPO_RM_AU","NOME_RM_AU"]))
        out["LABEL"] = out["TIPO_RM_AU"].str.upper().str.replace("IMEDIATA|INTERMEDIÁRIA","", regex=True).str.strip() + " — " + out["NOME_RM_AU"].astype(str)
        return out
    # Fallback: construir a partir de colunas legadas
    frames = []
    if "RM_NOME" in df.columns:
        a = df[["RM_NOME"]].dropna().drop_duplicates().rename(columns={"RM_NOME":"NOME"})
        a["TIPO"] = "RM"
        frames.append(a)
    if "AU_NOME" in df.columns:
        b = df[["AU_NOME"]].dropna().drop_duplicates().rename(columns={"AU_NOME":"NOME"})
        b["TIPO"] = "AU"
        frames.append(b)
    if not frames:
        return pd.DataFrame(columns=["TIPO_RM_AU","NOME_RM_AU","LABEL"])    
    c = pd.concat(frames, ignore_index=True)
    c = c.dropna().drop_duplicates().sort_values(["TIPO","NOME"]).reset_index(drop=True)
    c = c.rename(columns={"TIPO":"TIPO_RM_AU","NOME":"NOME_RM_AU"})
    c["LABEL"] = c["TIPO_RM_AU"] + " — " + c["NOME_RM_AU"].astype(str)
    return c

def _agg_long(df_long: pd.DataFrame) -> pd.DataFrame:
    piv = df_long.pivot_table(index="idade_grupo", columns="sexo", values="valor", aggfunc="sum", fill_value=0).reset_index()
    if "Masculino" not in piv.columns: piv["Masculino"] = 0
    if "Feminino" not in piv.columns: piv["Feminino"] = 0
    piv["Total_faixa"] = piv["Masculino"] + piv["Feminino"]
    return piv

def _pie_mf(m_total: int, f_total: int, title: str) -> go.Figure:
    fig = go.Figure(data=[go.Pie(labels=["Masculino","Feminino"], values=[m_total,f_total], hole=0.3)])
    fig.update_layout(title=title, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig

# Escala de análise (ordem: Estado, RM/AU, RG Intermediária, RG Imediata, Município, Setores)
scale_options = ["Estado"]
has_rm_au = any(c in df.columns for c in ["NOME_RM_AU","REGIAO_RM_AU"]) or any(c in df.columns for c in ["RM_NOME","AU_NOME"]) or {"TIPO_RM_AU","NOME_RM_AU"}.issubset(df.columns)
has_rgint = "NM_RGINT" in df.columns
has_rgi = "NM_RGI" in df.columns
if has_rm_au: scale_options.append("RM/AU")
if has_rgint: scale_options.append("Região Intermediária")
if has_rgi: scale_options.append("Região Imediata")
if set(["CD_MUN","NM_MUN"]).issubset(df.columns):
    scale_options.extend(["Município","Setores"])    
sel_scale = st.selectbox("Escala de Análise", options=scale_options, index=0)

def _wrap_title(texto: str, width: int = 42) -> str:
    try:
        import textwrap
        parts = textwrap.wrap(str(texto), width=width)
        return "<br>".join(parts) if parts else str(texto)
    except Exception:
        return str(texto)

def _plot_area(df_group: pd.DataFrame, titulo: str):
    if hasattr(st, "status"):
        with st.status("Preparando visualizações…", expanded=False) as st_status:
            prog = st.progress(0, text="Agregando dados…")
            df_plot = aggregate_pyramid(df_group, group_by=[])
            prog.progress(35, text="Calculando totais…")
            tbl = _agg_long(df_plot)
            m_total = int(df_plot[df_plot["sexo"]=="Masculino"]["valor"].sum())
            f_total = int(df_plot[df_plot["sexo"]=="Feminino"]["valor"].sum())
            total_decl = int(pd.to_numeric(df_group.get("V0001"), errors="coerce").fillna(0).sum()) if "V0001" in df_group.columns else None
            prog.progress(65, text="Gerando gráficos…")
            a,b = st.columns([2,1])
            a.plotly_chart(make_age_pyramid(df_plot, title=_wrap_title(titulo)), use_container_width=True)
            b.plotly_chart(_pie_mf(m_total,f_total,_wrap_title("Sexo — " + titulo.split(" — ")[-1])), use_container_width=True)
            prog.progress(85, text="Montando tabela…")
            st.dataframe(tbl, use_container_width=True)
            if total_decl is not None:
                diff = int(tbl["Total_faixa"].sum()) - total_decl
                pct = (diff/total_decl*100) if total_decl else None
                st.caption(f"Diferença (M+F − V0001): {diff:+,}" + (f" ({pct:.3f}% do V0001)" if pct is not None else ""))
            prog.progress(100)
            st_status.update(label="Visualizações prontas", state="complete")
    else:
        with st.spinner("Preparando visualizações…"):
            df_plot = aggregate_pyramid(df_group, group_by=[])
            tbl = _agg_long(df_plot)
            m_total = int(df_plot[df_plot["sexo"]=="Masculino"]["valor"].sum())
            f_total = int(df_plot[df_plot["sexo"]=="Feminino"]["valor"].sum())
            total_decl = int(pd.to_numeric(df_group.get("V0001"), errors="coerce").fillna(0).sum()) if "V0001" in df_group.columns else None
            a,b = st.columns([2,1])
            a.plotly_chart(make_age_pyramid(df_plot, title=_wrap_title(titulo)), use_container_width=True)
            b.plotly_chart(_pie_mf(m_total,f_total,_wrap_title("Sexo — " + titulo.split(" — ")[-1])), use_container_width=True)
            st.dataframe(tbl, use_container_width=True)
            if total_decl is not None:
                diff = int(tbl["Total_faixa"].sum()) - total_decl
                pct = (diff/total_decl*100) if total_decl else None
                st.caption(f"Diferença (M+F − V0001): {diff:+,}" + (f" ({pct:.3f}% do V0001)" if pct is not None else ""))

# Fluxo por escala
if sel_scale == "Estado":
    n_set = int(df.get("CD_SETOR", pd.Series()).nunique() if "CD_SETOR" in df.columns else 0)
    st.caption(f"Agregando Estado de SP — setores considerados: {n_set:,}.")
    _plot_area(df, "Pirâmide — Estado")

elif sel_scale == "RM/AU" and has_rm_au:
    rmau_df = _mk_rm_au_options(df)
    if rmau_df.empty:
        st.warning("Não há informações de RM/AU na base.")
        st.stop()
    sel = st.selectbox("Região (RM/AU) — selecione ou digite", options=rmau_df.index.tolist(), format_func=lambda i: rmau_df.loc[i, "LABEL"], key="sel_rmau")
    rec = rmau_df.loc[sel]
    if {"TIPO_RM_AU","NOME_RM_AU"}.issubset(df.columns):
        mask = (df["TIPO_RM_AU"].str.upper()==str(rec["TIPO_RM_AU"]).upper()) & (df["NOME_RM_AU"]==rec["NOME_RM_AU"])    
        df_group = df[mask]
    else:
        if str(rec["TIPO_RM_AU"]).upper()=="RM" and "RM_NOME" in df.columns:
            df_group = df[df["RM_NOME"]==rec["NOME_RM_AU"]]
        elif str(rec["TIPO_RM_AU"]).upper()=="AU" and "AU_NOME" in df.columns:
            df_group = df[df["AU_NOME"]==rec["NOME_RM_AU"]]
        else:
            df_group = df.head(0)
    n_set = int(df_group.get("CD_SETOR", pd.Series()).nunique() if "CD_SETOR" in df_group.columns else 0)
    st.caption(f"Agregando {rec['LABEL']} — setores: {n_set:,}.")
    _plot_area(df_group, f"Pirâmide — {rec['LABEL']}")

elif sel_scale == "Região Intermediária" and has_rgint:
    lst = sorted([x for x in df["NM_RGINT"].dropna().unique().tolist()])
    if not lst:
        st.warning("Sem valores de Região Intermediária.")
        st.stop()
    sel = st.selectbox("Região Intermediária — selecione ou digite", options=lst, key="sel_rgint")
    df_group = df[df["NM_RGINT"]==sel]
    n_set = int(df_group.get("CD_SETOR", pd.Series()).nunique() if "CD_SETOR" in df_group.columns else 0)
    st.caption(f"Agregando Região Intermediária — {sel} — setores: {n_set:,}.")
    _plot_area(df_group, f"Pirâmide — Região Intermediária: {sel}")

elif sel_scale == "Região Imediata" and has_rgi:
    lst = sorted([x for x in df["NM_RGI"].dropna().unique().tolist()])
    if not lst:
        st.warning("Sem valores de Região Imediata.")
        st.stop()
    sel = st.selectbox("Região Imediata — selecione ou digite", options=lst, key="sel_rgi")
    df_group = df[df["NM_RGI"]==sel]
    n_set = int(df_group.get("CD_SETOR", pd.Series()).nunique() if "CD_SETOR" in df_group.columns else 0)
    st.caption(f"Agregando Região Imediata — {sel} — setores: {n_set:,}.")
    _plot_area(df_group, f"Pirâmide — Região Imediata: {sel}")

elif sel_scale in ("Município","Setores") and set(["CD_MUN","NM_MUN"]).issubset(df.columns):
    mun_df = _mk_municipios(df)
    name_map = dict(zip(mun_df["CD_MUN"], mun_df["NM_MUN"]))
    _fmt_m = lambda c: "— selecione ou digite —" if c is None else (str(c) + " — " + (name_map.get(c, "") or ""))
    sel_mun = st.selectbox("Município — selecione ou digite", options=[None]+mun_df["CD_MUN"].tolist(), format_func=_fmt_m, key="sel_mun")
    if sel_mun is None:
        st.info("Selecione um município.")
        st.stop()
    df_scope = df[df["CD_MUN"]==sel_mun]
    n_set = int(df_scope.get("CD_SETOR", pd.Series()).nunique() if "CD_SETOR" in df_scope.columns else 0)
    st.caption(f"Município: {name_map.get(sel_mun,'')} — setores disponíveis: {n_set:,}.")

    if sel_scale == "Município":
        # Opção de desagregar por setores do município
        desag = st.checkbox("Desagregar por setores do município", value=False, key="mun_desag")
        if not desag:
            _plot_area(df_scope, "Pirâmide — Município")
        else:
            # Escolher um setor específico dentro do município
            set_df = df_scope[["CD_SETOR"]].dropna().drop_duplicates().sort_values("CD_SETOR") if "CD_SETOR" in df_scope.columns else pd.DataFrame(columns=["CD_SETOR"])            
            sel_setor = st.selectbox("Setor do Município — selecione ou digite", options=[None]+set_df["CD_SETOR"].tolist(), key="sel_setor_mun")
            if sel_setor is None:
                st.stop()
            df_sector = df_scope[df_scope["CD_SETOR"]==sel_setor]
            _plot_area(df_sector, f"Pirâmide — Setor {sel_setor}")
    else:
        # Escala "Setores": escolher diretamente um setor
        set_df = df_scope[["CD_SETOR"]].dropna().drop_duplicates().sort_values("CD_SETOR") if "CD_SETOR" in df_scope.columns else pd.DataFrame(columns=["CD_SETOR"])        
        sel_setor = st.selectbox("Setor — selecione ou digite", options=[None]+set_df["CD_SETOR"].tolist(), key="sel_setor")
        if sel_setor is None:
            st.stop()
        df_sector = df_scope[df_scope["CD_SETOR"]==sel_setor]
        _plot_area(df_sector, f"Pirâmide — Setor {sel_setor}")
else:
    st.warning("Seleção inválida para a base atual.")
