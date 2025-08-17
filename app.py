
import sys
from pathlib import Path as _P
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

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

st.set_page_config(page_title="Senso&Censo - Explorador de dados censitários", layout="wide")

render_topbar()

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

path_default = r"D:\\repo\\saida_parquet\\base_integrada_final.parquet"
parquet_path = st.text_input("Parquet (SP)", st.session_state.get("parquet_path", path_default), key="parquet_path", help="Você pode digitar o caminho do arquivo Parquet ou colar/editar manualmente.")
parquet_path = _norm(parquet_path)

@st.cache_data(show_spinner=True, ttl=3600)
def _load(path: str) -> pd.DataFrame:
    return load_sp_age_sex_enriched(path, limit=None, verbose=False, uf_code="35")

try:
    df = _load(parquet_path)
    st.success(f"{len(df):,} linhas (SP) carregadas.")
except Exception as e:
    st.error(f"Falha ao ler Parquet: {e}")
    st.stop()

# debug indicators
dbg_cols = []
for nm in ["RM_NOME","AU_NOME","NM_RGINT","NM_RGI","CD_SITUACAO","SITUACAO_DET_TXT"]:
    if nm in df.columns:
        non_na = int(df[nm].notna().sum())
        dbg_cols.append(f"{nm}: {non_na} preenchidos")
if dbg_cols:
    st.caption("Colunas regionais/detalhe detectadas → " + " | ".join(dbg_cols))

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

left, right = st.columns([3,2])

with left:
    if set(["CD_MUN","NM_MUN"]).issubset(df.columns):
        mun_df = df[["CD_MUN","NM_MUN"]].dropna().drop_duplicates().sort_values(["NM_MUN","CD_MUN"])
        name_map = dict(zip(mun_df["CD_MUN"], mun_df["NM_MUN"]))
        _fmt = lambda c: "— selecione —" if c is None else (str(c) + " — " + (name_map.get(c, "") or ""))
        sel_mun = st.selectbox("Município (digite ou selecione)", options=[None]+mun_df["CD_MUN"].tolist(),
                               format_func=_fmt,
                               key="sel_mun", help="Dica: comece a digitar o nome ou o código para filtrar.")
        if sel_mun is None:
            st.info("Selecione um município para continuar.")
            st.stop()
        df_scope = df[df["CD_MUN"] == sel_mun]
        st.caption("Setores neste município (após filtros acima): **{}** setores únicos.".format(int(df_scope.get("CD_SETOR", pd.Series()).nunique() if "CD_SETOR" in df_scope.columns else 0)))
    else:
        st.error("Colunas CD_MUN/NM_MUN ausentes.")
        st.stop()

with right:
    agg_opts = ["Setor específico","Município (total)"]
    has_rm = any(c in df.columns for c in ["RM_NOME","AU_NOME"])
    has_rgint = "NM_RGINT" in df.columns
    has_rgi = "NM_RGI" in df.columns
    if has_rm: agg_opts.append("RM/AU")
    if has_rgint: agg_opts.append("Região Geográfica Intermediária")
    if has_rgi: agg_opts.append("Região Geográfica Imediata")
    sel_agg = st.selectbox("Agregação", agg_opts, index=1 if "Município (total)" in agg_opts else 0)

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

if sel_agg == "Município (total)":
    df_plot = aggregate_pyramid(df_scope, group_by=[])
    n_set = int(df_scope.get("CD_SETOR", pd.Series()).nunique() if "CD_SETOR" in df_scope.columns else 0)
    st.caption("Agregando **{}** setores do município selecionado.".format(n_set))
    tbl = _agg_long(df_plot)
    m_total = int(df_plot[df_plot["sexo"]=="Masculino"]["valor"].sum())
    f_total = int(df_plot[df_plot["sexo"]=="Feminino"]["valor"].sum())
    total_decl = int(pd.to_numeric(df_scope.get("V0001"), errors="coerce").fillna(0).sum()) if "V0001" in df_scope.columns else None
    a,b = st.columns([2,1])
    a.plotly_chart(make_age_pyramid(df_plot, title="Pirâmide — Município"), use_container_width=True)
    b.plotly_chart(_pie_mf(m_total,f_total,"Sexo — Município"), use_container_width=True)
    st.dataframe(tbl, use_container_width=True)
    if total_decl is not None:
        diff = int(tbl["Total_faixa"].sum()) - total_decl
        pct = (diff/total_decl*100) if total_decl else None
        st.caption(f"Diferença (M+F − V0001): {diff:+,}" + (f" ({pct:.3f}% do V0001)" if pct is not None else ""))

elif sel_agg == "Setor específico":
    label_det = "SITUACAO_DET_TXT" if "SITUACAO_DET_TXT" in df_scope.columns else None
    cols_sel = ["CD_SETOR"] + ([label_det] if label_det else [])
    set_df = df_scope[cols_sel].dropna().drop_duplicates().sort_values("CD_SETOR")
    det_map = dict(zip(set_df["CD_SETOR"], set_df[label_det])) if label_det else {}
    _fmt_setor = (lambda c: "— selecione —" if c is None else (str(c) + " — " + (det_map.get(c, "") or ""))) if det_map else (lambda c: "— selecione —" if c is None else str(c))
    sel_setor = st.selectbox("Setor (digite ou selecione)", options=[None]+set_df["CD_SETOR"].tolist(),
                             format_func=_fmt_setor,
                             key="sel_setor")
    if sel_setor is None: st.stop()
    df_sector = df_scope[df_scope["CD_SETOR"]==sel_setor]
    df_plot = aggregate_pyramid(df_sector, group_by=[])
    tbl = _agg_long(df_plot)
    m_total = int(df_plot[df_plot["sexo"]=="Masculino"]["valor"].sum())
    f_total = int(df_plot[df_plot["sexo"]=="Feminino"]["valor"].sum())
    total_decl = None
    if "V0001" in df_sector.columns:
        uniq = pd.to_numeric(df_sector["V0001"], errors="coerce").dropna().unique()
        total_decl = int(uniq[0]) if len(uniq)==1 else int(pd.to_numeric(df_sector["V0001"], errors="coerce").fillna(0).sum())
    a,b = st.columns([2,1])
    a.plotly_chart(make_age_pyramid(df_plot, title="Pirâmide — Setor " + str(sel_setor)), use_container_width=True)
    b.plotly_chart(_pie_mf(m_total,f_total,"Sexo — Setor"), use_container_width=True)
    st.dataframe(tbl, use_container_width=True)
    if total_decl is not None:
        diff = int(tbl["Total_faixa"].sum()) - total_decl
        pct = (diff/total_decl*100) if total_decl else None
        st.caption(f"Diferença (M+F − V0001): {diff:+,}" + (f" ({pct:.3f}% do V0001)" if pct is not None else ""))

else:
    # Region-wide: infer label from selected município, then aggregate across *all* municípios daquela região, respeitando filtros aplicados.
    if sel_agg == "RM/AU":
        label_col = "RM_NOME" if "RM_NOME" in df.columns else ("AU_NOME" if "AU_NOME" in df.columns else None)
    elif sel_agg == "Região Geográfica Intermediária":
        label_col = "NM_RGINT" if "NM_RGINT" in df.columns else None
    else:
        label_col = "NM_RGI" if "NM_RGI" in df.columns else None
    if not label_col:
        st.warning("Colunas para este tipo de agregação não foram encontradas na base.")
        st.stop()
    reg_vals = df_scope[label_col].dropna().unique().tolist()
    if not reg_vals:
        st.warning("O município selecionado não possui valor em " + label_col + ".")
        st.stop()
    reg_val = reg_vals[0]
    df_group = df[df[label_col] == reg_val]
    n_set = int(df_group.get("CD_SETOR", pd.Series()).nunique() if "CD_SETOR" in df_group.columns else 0)
    st.caption("Agregando **{}** setores em {}: **{}**.".format(n_set, sel_agg, str(reg_val)))
    df_plot = aggregate_pyramid(df_group, group_by=[])
    tbl = _agg_long(df_plot)
    m_total = int(df_plot[df_plot["sexo"]=="Masculino"]["valor"].sum())
    f_total = int(df_plot[df_plot["sexo"]=="Feminino"]["valor"].sum())
    total_decl = int(pd.to_numeric(df_group.get("V0001"), errors="coerce").fillna(0).sum()) if "V0001" in df_group.columns else None
    a,b = st.columns([2,1])
    a.plotly_chart(make_age_pyramid(df_plot, title="Pirâmide — " + sel_agg + ": " + str(reg_val)), use_container_width=True)
    b.plotly_chart(_pie_mf(m_total,f_total,"Sexo — " + sel_agg), use_container_width=True)
    st.dataframe(tbl, use_container_width=True)
    if total_decl is not None:
        diff = int(tbl["Total_faixa"].sum()) - total_decl
        pct = (diff/total_decl*100) if total_decl else None
        st.caption(f"Diferença (M+F − V0001): {diff:+,}" + (f" ({pct:.3f}% do V0001)" if pct is not None else ""))
