import streamlit as st
import pandas as pd
import os
from pathlib import Path

@st.cache_data(show_spinner=True, ttl=60*60*24*365*10)  # 10 anos
def carregar_dados():
    fonte = st.session_state.get("fonte_dados", "parquet")
    if fonte == "parquet":
        parquet_path = st.session_state.get("parquet_path", r"D:\repo\saida_parquet\base_integrada_final.parquet")
        if not Path(parquet_path).exists():
            st.error(f"Arquivo Parquet não encontrado: {parquet_path}")
            st.stop()
        return pd.read_parquet(parquet_path)
    else:
        import duckdb
        token = os.environ.get("motherduck_token")
        if not token:
            st.error("Token MotherDuck não encontrado. Configure a variável de ambiente motherduck_token.")
            st.stop()
        db = st.session_state.get("md_db", "sensocenso")
        table = st.session_state.get("md_table", "censo2022")
        con = duckdb.connect(f"md:{db}")
        query = f"SELECT * FROM {table} LIMIT 10000"
        df = con.execute(query).fetchdf()
        con.close()
        return df

st.set_page_config(layout="wide")
st.title("Demografia — Pirâmide Etária (Fonte definida em Config)")

if "fonte_dados" not in st.session_state:
    st.warning("Defina a fonte de dados em 'Configuração de Fonte'.")
    st.stop()


try:
    df = carregar_dados()
    st.success(f"{len(df):,} linhas carregadas da fonte '{st.session_state['fonte_dados']}'.")

    # Filtros dinâmicos
    with st.expander("Filtros", expanded=True):
        c1, c2, c3 = st.columns(3)
        if "SITUACAO" in df.columns:
            macro_opts = sorted([x for x in df["SITUACAO"].dropna().unique().tolist() if x in ("Urbana","Rural")]) or ["Urbana","Rural"]
            sel_macro = c1.multiselect("Situação (Urbana/Rural)", macro_opts, default=macro_opts, key="sel_macro_demog")
            if sel_macro: df = df[df["SITUACAO"].isin(sel_macro)]
        if "CD_SITUACAO" in df.columns:
            from censo_app.transform import SITUACAO_DET_MAP
            sit_opts = list(SITUACAO_DET_MAP.items())
            sel_sit = c2.multiselect("Situação detalhada (CD_SITUACAO)", sit_opts, default=[k for k,_ in sit_opts], format_func=lambda t: f"{t[0]} — {t[1]}", key="sel_sit_demog")
            if sel_sit: df = df[df["CD_SITUACAO"].isin(sel_sit)]
        if "CD_TIPO" in df.columns:
            from censo_app.transform import TIPO_MAP
            tipo_opts = list(TIPO_MAP.items())
            sel_tipo = c3.multiselect("Tipo do Setor (CD_TIPO)", tipo_opts, default=[k for k,_ in tipo_opts], format_func=lambda t: f"{t[0]} — {t[1]}", key="sel_tipo_demog")
            if sel_tipo: df = df[df["CD_TIPO"].isin(sel_tipo)]

    st.write("### Amostra dos dados filtrados")
    st.dataframe(df.head(100))

    # Indicadores demográficos
    st.markdown("### Indicadores Demográficos (município ou total)")
    from censo_app.indicadores_demograficos import calcular_indicadores_df
    from censo_app.transform import VARIAVEL_DESCRICAO
    if {"idade_grupo", "sexo", "valor"} <= set(df.columns):
        indicadores = calcular_indicadores_df(df)
        for var, val in indicadores.items():
            desc = VARIAVEL_DESCRICAO.get(var, "")
            st.write(f"**{var}:** {val:.3f}  ", f"<span title='{desc}'>ℹ️</span>", unsafe_allow_html=True)
    else:
        st.info("Dados não estão no formato esperado para cálculo de indicadores.")

    # Gráfico de pirâmide etária
    st.markdown("### Pirâmide Etária (total filtrado)")
    if {"idade_grupo", "sexo", "valor"} <= set(df.columns):
        from censo_app.viz import make_age_pyramid
        import plotly.graph_objects as go
        df_plot = df.groupby(["idade_grupo","sexo"], as_index=False)["valor"].sum()
        fig = make_age_pyramid(df_plot, title="Pirâmide etária — total filtrado")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Dados não estão no formato esperado para pirâmide etária.")

    st.markdown("### Exportação de dados")
    if st.button("Exportar JSON (amostra)"):
        st.download_button(
            label="Baixar JSON",
            data=df.head(100).to_json(orient="records", force_ascii=False, indent=2),
            file_name="amostra_demografia.json",
            mime="application/json"
        )
except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
