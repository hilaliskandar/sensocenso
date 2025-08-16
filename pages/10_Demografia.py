import sys
from pathlib import Path as _P
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

SRC = _P(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from censo_app.transform import (
    load_sp_age_sex_enriched, aggregate_pyramid, wide_to_long_pyramid, merge_rm_au_from_excel,
    SITUACAO_DET_MAP, TIPO_MAP, VARIAVEL_DESCRICAO
)
from censo_app.indicadores_demograficos import calcular_indicadores_df
from censo_app.viz import make_age_pyramid

st.set_page_config(layout="wide")
st.title("🏛️ Demografia — Análise Populacional Avançada — v2.0")

with st.sidebar:
    keepalive = st.checkbox("Evitar expirar (autorefresh a cada 5 min)", value=False)
    if keepalive and st_autorefresh:
        st_autorefresh(interval=5*60*1000, key="demografia_refresh")

def _norm(s: str) -> str:
    return (s or "").strip().strip('"').strip("'").replace("\\", "/")

# Inputs
parquet_path = st.text_input("Parquet (SP)", r"D:\\repo\\saida_parquet\\base_integrada_final.parquet", key="path_parquet_demog")
rm_xlsx_path = st.text_input("Excel RM/AU (opcional)", r"D:\\repo\\insumos\\Composicao_RM_2024.xlsx", key="path_rm_demog")
parquet_path = _norm(parquet_path)
rm_xlsx_path = _norm(rm_xlsx_path)

col1, col2, col3, col4 = st.columns([1,1,1,1])
with col1:
    use_limit = st.checkbox("Amostra limitada", value=False, key="use_limit_demog")
with col2:
    limit = st.number_input("Limite", min_value=1, value=10000, key="limit_demog") if use_limit else None
with col3:
    use_rm_au = st.checkbox("Incluir RM/AU", value=True, key="use_rm_au_demog")
with col4:
    go_load = st.button("🔄 Carregar dados", key="load_demog")

@st.cache_data(show_spinner=True, ttl=3600)
def _load_data(parquet_path: str, limit: int = None, use_rm: bool = False, rm_path: str = None):
    df = load_sp_age_sex_enriched(parquet_path, limit=limit, verbose=False, uf_code="35")
    
    if use_rm and rm_path and _P(rm_path).exists():
        try:
            df = merge_rm_au_from_excel(df, rm_path)
            st.success("✅ Dados RM/AU incorporados")
        except Exception as e:
            st.warning(f"⚠️ Falha ao incorporar RM/AU: {e}")
    
    return df

if go_load or "df_wide_demog" not in st.session_state:
    try:
        df_wide = _load_data(parquet_path, limit, use_rm_au, rm_xlsx_path if use_rm_au else None)
        st.session_state["df_wide_demog"] = df_wide
        st.success(f"✅ {len(df_wide):,} setores carregados")
    except Exception as e:
        st.error(f"❌ Erro ao carregar: {e}")
        st.stop()
else:
    df_wide = st.session_state["df_wide_demog"]
    st.info(f"📊 {len(df_wide):,} setores em memória")

# Conversão para formato long para análise
df_long = wide_to_long_pyramid(df_wide)

st.divider()
st.subheader("🔍 Filtros Avançados")

# Layout de filtros em colunas
c1, c2, c3, c4 = st.columns(4)

# Filtro 1: Situação Urbana/Rural (padrão: Urbana)
with c1:
    if "SITUACAO" in df_long.columns:
        sit_opts = sorted([x for x in df_long["SITUACAO"].dropna().unique() if x in ("Urbana", "Rural")])
        default_sit = ["Urbana"]  # Padrão: apenas Urbana
        sel_situacao = st.multiselect("Situação", sit_opts, default=default_sit, key="fil_situacao_demog")
        if sel_situacao:
            df_long = df_long[df_long["SITUACAO"].isin(sel_situacao)]

# Filtro 2: Tipo de Setor (padrão: 0 e 1)
with c2:
    if "CD_TIPO" in df_long.columns:
        tipo_opts = list(TIPO_MAP.items())
        default_tipo = [0, 1]  # Padrão: Não especial e Favela/Comunidade
        sel_tipo = st.multiselect("Tipo de Setor", tipo_opts, 
                                 default=[item for item in tipo_opts if item[0] in default_tipo],
                                 format_func=lambda x: f"{x[0]} — {x[1]}", key="fil_tipo_demog")
        if sel_tipo:
            df_long = df_long[df_long["CD_TIPO"].isin([k for k, _ in sel_tipo])]

# Filtro 3: Região Metropolitana (se disponível)
with c3:
    if "CD_RM" in df_long.columns:
        rm_opts = sorted([x for x in df_long["CD_RM"].dropna().unique()])
        if rm_opts:
            sel_rm = st.multiselect("Região Metropolitana", ["Todas"] + rm_opts, 
                                   default=["Todas"], key="fil_rm_demog")
            if "Todas" not in sel_rm and sel_rm:
                df_long = df_long[df_long["CD_RM"].isin(sel_rm)]

# Filtro 4: Aglomeração Urbana (se disponível)
with c4:
    if "CD_AU" in df_long.columns:
        au_opts = sorted([x for x in df_long["CD_AU"].dropna().unique()])
        if au_opts:
            sel_au = st.multiselect("Aglomeração Urbana", ["Todas"] + au_opts,
                                   default=["Todas"], key="fil_au_demog")
            if "Todas" not in sel_au and sel_au:
                df_long = df_long[df_long["CD_AU"].isin(sel_au)]

st.write(f"**Dados filtrados:** {len(df_long):,} registros")

st.divider()
st.subheader("📊 Análise Demográfica")

# Seleção do nível de análise
nivel = st.radio("Nível de análise:", 
                ["Estado (SP)", "Região Metropolitana", "Aglomeração Urbana", "Município", "Setor"],
                horizontal=True, key="nivel_demog")

# Lógica de seleção baseada no nível
if nivel == "Estado (SP)":
    df_analysis = df_long
    title_suffix = "Estado de São Paulo"
    
elif nivel == "Região Metropolitana" and "CD_RM" in df_long.columns:
    rm_options = sorted([x for x in df_long["CD_RM"].dropna().unique()])
    if rm_options:
        sel_rm_analysis = st.selectbox("Selecione a RM:", rm_options, key="sel_rm_analysis")
        df_analysis = df_long[df_long["CD_RM"] == sel_rm_analysis]
        title_suffix = f"RM {sel_rm_analysis}"
    else:
        st.warning("Nenhuma RM disponível nos dados filtrados")
        st.stop()
        
elif nivel == "Aglomeração Urbana" and "CD_AU" in df_long.columns:
    au_options = sorted([x for x in df_long["CD_AU"].dropna().unique()])
    if au_options:
        sel_au_analysis = st.selectbox("Selecione a AU:", au_options, key="sel_au_analysis")
        df_analysis = df_long[df_long["CD_AU"] == sel_au_analysis]
        title_suffix = f"AU {sel_au_analysis}"
    else:
        st.warning("Nenhuma AU disponível nos dados filtrados")
        st.stop()
        
elif nivel == "Município":
    if all(c in df_long.columns for c in ["CD_MUN", "NM_MUN"]):
        mun_df = df_long[["CD_MUN", "NM_MUN"]].dropna().drop_duplicates().sort_values("NM_MUN")
        mun_options = [f"{row.CD_MUN} — {row.NM_MUN}" for row in mun_df.itertuples(index=False)]
        sel_mun_label = st.selectbox("Selecione o município:", mun_options, key="sel_mun_analysis")
        sel_mun_cod = int(sel_mun_label.split(" — ")[0])
        df_analysis = df_long[df_long["CD_MUN"] == sel_mun_cod]
        title_suffix = sel_mun_label
    else:
        st.error("Colunas de município não disponíveis")
        st.stop()
        
elif nivel == "Setor":
    if all(c in df_long.columns for c in ["CD_MUN", "NM_MUN"]):
        # Primeiro seleciona município
        mun_df = df_long[["CD_MUN", "NM_MUN"]].dropna().drop_duplicates().sort_values("NM_MUN")
        mun_options = [f"{row.CD_MUN} — {row.NM_MUN}" for row in mun_df.itertuples(index=False)]
        sel_mun_label = st.selectbox("Município:", mun_options, key="sel_mun_setor")
        sel_mun_cod = int(sel_mun_label.split(" — ")[0])
        
        # Depois seleciona setor
        setores_df = df_long[df_long["CD_MUN"] == sel_mun_cod]
        setor_options = sorted(setores_df["CD_SETOR"].dropna().unique())
        sel_setor = st.selectbox("Setor:", setor_options, key="sel_setor_analysis")
        df_analysis = df_long[df_long["CD_SETOR"] == sel_setor]
        title_suffix = f"Setor {sel_setor}"
    else:
        st.error("Colunas de setor não disponíveis")
        st.stop()

else:
    df_analysis = df_long
    title_suffix = "Total filtrado"

# Agregação dos dados para visualização
df_plot = aggregate_pyramid(df_analysis, group_by=[])

if df_plot.empty:
    st.warning("⚠️ Nenhum dado disponível para os filtros selecionados")
    st.stop()

# Layout em colunas para visualizações
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("🔺 Pirâmide Etária")
    fig = make_age_pyramid(df_plot, title=f"Demografia — {title_suffix}")
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.subheader("📈 Resumo Populacional")
    total_pop = int(df_plot["valor"].sum())
    pop_masc = int(df_plot[df_plot["sexo"] == "Masculino"]["valor"].sum())
    pop_fem = int(df_plot[df_plot["sexo"] == "Feminino"]["valor"].sum())
    
    st.metric("População Total", f"{total_pop:,}")
    st.metric("População Masculina", f"{pop_masc:,}", f"{pop_masc/total_pop*100:.1f}%")
    st.metric("População Feminina", f"{pop_fem:,}", f"{pop_fem/total_pop*100:.1f}%")
    
    # Gráfico de pizza
    fig_pie = go.Figure(data=[go.Pie(labels=["Masculino", "Feminino"], 
                                    values=[pop_masc, pop_fem], 
                                    hole=0.3)])
    fig_pie.update_layout(title="Distribuição por Sexo", height=300)
    st.plotly_chart(fig_pie, use_container_width=True)

st.divider()
st.subheader("📊 Indicadores Demográficos Avançados")

# Para calcular indicadores, precisamos converter para formato de idades individuais
# Vamos usar uma aproximação baseada nas faixas etárias
def convert_age_groups_to_individual_ages(df_plot):
    """
    Converte faixas etárias para idades individuais aproximadas para cálculo de indicadores.
    """
    age_mapping = {
        "0 a 4 anos": list(range(0, 5)),
        "5 a 9 anos": list(range(5, 10)),
        "10 a 14 anos": list(range(10, 15)),
        "15 a 19 anos": list(range(15, 20)),
        "20 a 24 anos": list(range(20, 25)),
        "25 a 29 anos": list(range(25, 30)),
        "30 a 39 anos": list(range(30, 40)),
        "40 a 49 anos": list(range(40, 50)),
        "50 a 59 anos": list(range(50, 60)),
        "60 a 69 anos": list(range(60, 70)),
        "70 anos ou mais": list(range(70, 101))  # Até 100 anos
    }
    
    result_rows = []
    for _, row in df_plot.iterrows():
        faixa = row["idade_grupo"]
        if faixa in age_mapping:
            idades = age_mapping[faixa]
            valor_por_idade = row["valor"] / len(idades)  # Distribui igualmente
            for idade in idades:
                result_rows.append({
                    "idade": idade,
                    "sexo": row["sexo"],
                    "pop": valor_por_idade
                })
    
    return pd.DataFrame(result_rows)

# Converter para formato de indicadores
df_indicators = convert_age_groups_to_individual_ages(df_plot)

if not df_indicators.empty:
    try:
        # Calcular indicadores demográficos
        from censo_app.indicadores_demograficos import calcular_populacoes_agrupadas, calcular_indicadores_demograficos, gerar_flags_qualidade
        
        grupos = calcular_populacoes_agrupadas(df_indicators, idade_col='idade', sexo_col='sexo', pop_col='pop')
        indicadores = calcular_indicadores_demograficos(grupos)
        flags = gerar_flags_qualidade(grupos)
        
        # Exibir indicadores em colunas
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**Razões de Dependência**")
            for ind in ["RDT", "RDJ", "RDI"]:
                if ind in indicadores:
                    desc = VARIAVEL_DESCRICAO.get(ind, "")
                    st.write(f"**{ind}:** {indicadores[ind]:.2f}")
                    st.caption(desc)
        
        with col2:
            st.markdown("**Envelhecimento**")
            for ind in ["IE_60p", "IE_65p", "Prop_80p"]:
                if ind in indicadores:
                    desc = VARIAVEL_DESCRICAO.get(ind, "")
                    st.write(f"**{ind}:** {indicadores[ind]:.2f}")
                    st.caption(desc)
        
        with col3:
            st.markdown("**Apoio e Natalidade**")
            for ind in ["OADR", "PSR", "TBN_proxy"]:
                if ind in indicadores:
                    desc = VARIAVEL_DESCRICAO.get(ind, "")
                    st.write(f"**{ind}:** {indicadores[ind]:.2f}")
                    st.caption(desc)
        
        # Alertas de qualidade
        if any(flags.values()):
            st.warning("⚠️ **Alertas de Qualidade:**")
            for flag, valor in flags.items():
                if valor:
                    if flag == "denominador_pequeno":
                        st.write("• População em idade ativa (15-64) < 500 pessoas - indicadores podem ser instáveis")
        
    except Exception as e:
        st.error(f"Erro ao calcular indicadores: {e}")

st.divider()
st.subheader("📋 Dados Detalhados")

# Tabela com dados agregados
st.dataframe(df_plot, use_container_width=True)

# Opções de exportação
st.subheader("💾 Exportação")
col_exp1, col_exp2 = st.columns(2)

with col_exp1:
    if st.button("📄 Baixar CSV"):
        csv = df_plot.to_csv(index=False)
        st.download_button(
            label="Baixar dados CSV",
            data=csv,
            file_name=f"demografia_{title_suffix.replace(' ', '_')}.csv",
            mime="text/csv"
        )

with col_exp2:
    if st.button("📊 Baixar Indicadores"):
        if 'indicadores' in locals():
            ind_df = pd.DataFrame([{**grupos, **indicadores, **flags}])
            csv_ind = ind_df.to_csv(index=False)
            st.download_button(
                label="Baixar indicadores CSV",
                data=csv_ind,
                file_name=f"indicadores_{title_suffix.replace(' ', '_')}.csv",
                mime="text/csv"
            )