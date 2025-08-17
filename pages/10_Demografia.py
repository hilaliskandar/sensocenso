import sys
from pathlib import Path as _P
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

# importar módulos centrais
ROOT = _P(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from censo_app.transform import (
    load_sp_age_sex_enriched, aggregate_pyramid, wide_to_long_pyramid,
    carregar_sp_idade_sexo_enriquecido, largura_para_longo_piramide, agregar_piramide,
)
from censo_app.viz import make_age_pyramid as _make_age_pyramid
from censo_app.ui import render_topbar
from config.config_loader import get_settings, get_page_config

# Mapeamentos simplificados para os filtros
# placeholders simples para rótulos (poderão vir do YAML futuramente)
TIPO_MAP = {0: "Não especial", 1: "Favela e Comunidade Urbana"}
SITUACAO_DET_MAP = {"Urbana": "Urbana", "Rural": "Rural"}

def _aggregate_local(df_long: pd.DataFrame) -> pd.DataFrame:
    return df_long.groupby(['sexo', 'faixa_etaria'], as_index=False)['populacao'].sum()

DEMOG_CFG = get_page_config('demografia')

def create_abnt_demographic_table(df_plot, title_suffix=""):
    """
    Cria tabela demográfica em padrão ABNT
    
    Estrutura:
    - Linhas: Faixas etárias
    - Colunas: Masculino | Feminino | Total | % Masculino | % Feminino
    """
    # Agrupar dados por faixa etária e sexo
    pivot_data = df_plot.pivot_table(
        index='faixa_etaria', 
        columns='sexo', 
        values='populacao', 
        aggfunc='sum', 
        fill_value=0
    ).reset_index()
    
    # Garantir que as colunas existam
    if 'Masculino' not in pivot_data.columns:
        pivot_data['Masculino'] = 0
    if 'Feminino' not in pivot_data.columns:
        pivot_data['Feminino'] = 0
    
    # Calcular totais e percentuais
    pivot_data['Total'] = pivot_data['Masculino'] + pivot_data['Feminino']
    
    # Calcular percentuais apenas onde Total > 0
    mask = pivot_data['Total'] > 0
    pivot_data['% Masculino'] = 0.0
    pivot_data['% Feminino'] = 0.0
    pivot_data.loc[mask, '% Masculino'] = (pivot_data.loc[mask, 'Masculino'] / pivot_data.loc[mask, 'Total'] * 100).round(1)
    pivot_data.loc[mask, '% Feminino'] = (pivot_data.loc[mask, 'Feminino'] / pivot_data.loc[mask, 'Total'] * 100).round(1)
    
    # Reordenar colunas para padrão ABNT
    abnt_table = pivot_data[['faixa_etaria', 'Masculino', 'Feminino', 'Total', '% Masculino', '% Feminino']].copy()
    
    # Renomear coluna para padrão ABNT
    abnt_table = abnt_table.rename(columns={'faixa_etaria': 'Faixa Etária'})
    
    # Ordenar por faixa etária (assumindo ordem natural)
    faixas_ordem = DEMOG_CFG.get('age_buckets_order', [
        "0 a 4 anos", "5 a 9 anos", "10 a 14 anos", "15 a 19 anos",
        "20 a 24 anos", "25 a 29 anos", "30 a 34 anos", "35 a 39 anos", 
        "40 a 44 anos", "45 a 49 anos", "50 a 54 anos", "55 a 59 anos",
        "60 a 64 anos", "65 a 69 anos", "70 anos ou mais"
    ])
    
    # Reordenar baseado na ordem padrão, mantendo faixas não mapeadas no final
    abnt_table['ordem'] = abnt_table['Faixa Etária'].apply(
        lambda x: faixas_ordem.index(x) if x in faixas_ordem else 999
    )
    abnt_table = abnt_table.sort_values('ordem').drop('ordem', axis=1)
    
    # Adicionar linha de totais
    total_masculino = abnt_table['Masculino'].sum()
    total_feminino = abnt_table['Feminino'].sum()
    total_geral = abnt_table['Total'].sum()
    
    total_row = {
        'Faixa Etária': 'TOTAL',
        'Masculino': total_masculino,
        'Feminino': total_feminino,
        'Total': total_geral,
        '% Masculino': (total_masculino / total_geral * 100).round(1) if total_geral > 0 else 0,
        '% Feminino': (total_feminino / total_geral * 100).round(1) if total_geral > 0 else 0
    }
    
    abnt_table = pd.concat([abnt_table, pd.DataFrame([total_row])], ignore_index=True)
    
    # Reset index para garantir que não há índices duplicados
    abnt_table = abnt_table.reset_index(drop=True)
    
    return abnt_table

def load_rm_au_data(csv_path="insumos/municipios_rm_au.csv"):
    """Carrega dados de RM/AU do CSV"""
    try:
        df_rm_au = pd.read_csv(csv_path)
        return df_rm_au
    except Exception:
        return None

def merge_rm_au_to_demographic_data(df_long, csv_path="insumos/municipios_rm_au.csv"):
    """Incorpora dados de RM/AU ao DataFrame demográfico"""
    df_rm_au = load_rm_au_data(csv_path)
    
    if df_rm_au is None:
        st.warning("⚠️ Arquivo de RM/AU não encontrado")
        return df_long
    
    # Mapear município -> RM/AU
    municipio_to_rm = {}
    municipio_to_au = {}
    
    for _, row in df_rm_au.iterrows():
        municipio = row['municipio'].upper()
        rm_au_name = row['rm_au']
        tipo = row['tipo']
        
        if tipo == 'RM':
            municipio_to_rm[municipio] = rm_au_name
        elif tipo == 'AU':
            municipio_to_au[municipio] = rm_au_name
    
    # Adicionar colunas RM/AU ao DataFrame
    df_result = df_long.copy()
    
    if 'NM_MUN' in df_result.columns:
        # Normalizar nomes de municípios
        df_result['NM_MUN_UPPER'] = df_result['NM_MUN'].str.upper()
        
        # Mapear RM e AU
        df_result['RM_NOME'] = df_result['NM_MUN_UPPER'].map(municipio_to_rm)
        df_result['AU_NOME'] = df_result['NM_MUN_UPPER'].map(municipio_to_au)
        
        # Remover coluna auxiliar
        df_result.drop('NM_MUN_UPPER', axis=1, inplace=True)
        
        # Mostrar estatísticas
        rm_count = df_result['RM_NOME'].notna().sum()
        au_count = df_result['AU_NOME'].notna().sum()
        
        if rm_count > 0:
            st.success(f"✅ RM incorporadas: {rm_count:,} registros, {df_result['RM_NOME'].nunique()} RMs únicas")
        if au_count > 0:
            st.success(f"✅ AU incorporadas: {au_count:,} registros, {df_result['AU_NOME'].nunique()} AUs únicas")
    else:
        st.error("❌ Coluna NM_MUN não encontrada nos dados")
    
    return df_result

def make_age_pyramid(df_plot, title="Pirâmide Etária"):
    """Criar gráfico de pirâmide etária usando Plotly"""
    import plotly.graph_objects as go
    
    # Separar dados por sexo
    df_masc = df_plot[df_plot['sexo'] == 'Masculino'].copy()
    df_fem = df_plot[df_plot['sexo'] == 'Feminino'].copy()
    
    # Fazer valores masculinos negativos para pirâmide
    df_masc['populacao'] = -df_masc['populacao']
    
    fig = go.Figure()
    
    # Lado masculino (esquerda)
    fig.add_trace(go.Bar(
        y=df_masc['faixa_etaria'],
        x=df_masc['populacao'],
        orientation='h',
        name='Masculino',
        marker=dict(color='blue'),
        text=df_masc['populacao'].abs(),
        textposition='auto'
    ))
    
    # Lado feminino (direita)
    fig.add_trace(go.Bar(
        y=df_fem['faixa_etaria'],
        x=df_fem['populacao'],
        orientation='h',
        name='Feminino',
        marker=dict(color='pink'),
        text=df_fem['populacao'],
        textposition='auto'
    ))
    
    fig.update_layout(
        title=title,
        xaxis_title="População",
        yaxis_title="Faixa Etária",
        barmode='overlay',
        height=600
    )
    
    return fig

st.set_page_config(layout="wide")
render_topbar(title="Senso&Censo — Demografia", subtitle="Censo 2022 — SP")
st.title("🏛️ Demografia — Análise Populacional Avançada — v2.0")

with st.sidebar:
    keepalive = st.checkbox("Evitar expirar (autorefresh a cada 5 min)", value=False)
    if keepalive and st_autorefresh:
        st_autorefresh(interval=5*60*1000, key="demografia_refresh")
    # Reset do contador de tabelas (sequencial por sessão/página)
    if st.button("🔁 Resetar contador de tabelas", use_container_width=True, key="reset_demog_table_seq_btn1"):
        st.session_state["demog_table_seq"] = 0

def _norm(s: str) -> str:
    return (s or "").strip().strip('"').strip("'").replace("\\", "/")

# Inputs
settings = get_settings()
parquet_default = settings.get('paths', {}).get('parquet_default', r"D:\\repo\\saida_parquet\\base_integrada_final.parquet")
rm_default = settings.get('paths', {}).get('rm_au_excel_default', r"D:\\repo\\insumos\\Composicao_RM_2024.xlsx")
parquet_path = st.text_input("Parquet (SP)", parquet_default, key="path_parquet_demog")
rm_xlsx_path = st.text_input("Excel RM/AU (opcional)", rm_default, key="path_rm_demog")
parquet_path = _norm(parquet_path)
rm_xlsx_path = _norm(rm_xlsx_path)

col1, col2, col3, col4 = st.columns([1,1,1,1])
with col1:
    use_limit = st.checkbox("Amostra limitada", value=False, key="use_limit_demog")
with col2:
    limit = st.number_input("Limite", min_value=1, value=10000, key="limit_demog") if use_limit else None
with col3:
    # RM/AU sempre incluídas como padrão
    use_rm_au = True
    st.info("ℹ️ RM/AU incluídas automaticamente")
with col4:
    go_load = st.button("🔄 Carregar dados", key="load_demog")

@st.cache_data(show_spinner=True, ttl=3600)
def _load_data(parquet_path: str, limit: int | None = None, excel_rm_au: str | None = None):
    df = carregar_sp_idade_sexo_enriquecido(parquet_path, limite=limit, detalhar=False, uf="35", caminho_excel=excel_rm_au)
    return df

if go_load or "df_wide_demog" not in st.session_state:
    try:
        df_wide = _load_data(parquet_path, limit, rm_xlsx_path if use_rm_au else None)
        st.session_state["df_wide_demog"] = df_wide
        st.success(f"✅ {len(df_wide):,} setores carregados")

        st.info(f"📊 Colunas disponíveis: {list(df_wide.columns)[:10]}...")
        if 'NM_MUN' in df_wide.columns:
            st.info(f"🏘️ Municípios: {df_wide['NM_MUN'].nunique()} únicos")
        if 'V0001' in df_wide.columns:
            st.info(f"👥 População total: {df_wide['V0001'].sum():,}")
    except Exception as e:
        st.error(f"❌ Erro ao carregar: {e}")
        st.stop()
else:
    df_wide = st.session_state["df_wide_demog"]
    st.info(f"📊 {len(df_wide):,} setores em memória")

# Conversão para formato long para análise
try:
    # Converter para formato longo com metadados
    df_long_full = largura_para_longo_piramide(df_wide)
    df_long = df_long_full.rename(columns={"idade_grupo": "faixa_etaria", "valor": "populacao"})
    st.success(f"✅ Formato long: {len(df_long):,} registros")
    
    # RM/AU já são incorporadas pelo loader via Excel quando disponível
    
    # Verificar se as colunas foram adicionadas com sucesso
    if 'RM_NOME' in df_long.columns:
        rms_count = df_long['RM_NOME'].notna().sum()
        rms_unique = df_long['RM_NOME'].nunique()
        st.success(f"✅ RM incorporadas: {rms_count:,} registros, {rms_unique} RMs únicas")
    
    if 'AU_NOME' in df_long.columns:
        aus_count = df_long['AU_NOME'].notna().sum()
        aus_unique = df_long['AU_NOME'].nunique()
        st.success(f"✅ AU incorporadas: {aus_count:,} registros, {aus_unique} AUs únicas")
        
except Exception as e:
    st.error(f"❌ Erro na conversão para formato long: {e}")
    st.stop()

st.divider()
st.subheader("🔍 Filtros Básicos")

# Layout de filtros em colunas
c1, c2, c3 = st.columns(3)

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

# Filtro 3: RM/AU (se disponível)
with c3:
    rm_au_options = []
    if "RM_NOME" in df_long.columns:
        rms = [f"RM: {x}" for x in sorted(df_long["RM_NOME"].dropna().unique())]
        rm_au_options.extend(rms)
    if "AU_NOME" in df_long.columns:
        aus = [f"AU: {x}" for x in sorted(df_long["AU_NOME"].dropna().unique())]
        rm_au_options.extend(aus)
    
    if rm_au_options:
        sel_rm_au_filter = st.multiselect("RM/AU", ["Todas"] + rm_au_options, 
                               default=["Todas"], key="fil_rm_au_demog")
        if "Todas" not in sel_rm_au_filter and sel_rm_au_filter:
            # Aplicar filtro baseado na seleção
            filter_condition = pd.Series([False] * len(df_long))
            for sel in sel_rm_au_filter:
                if sel.startswith("RM: "):
                    rm_name = sel[4:]
                    filter_condition |= (df_long["RM_NOME"] == rm_name)
                elif sel.startswith("AU: "):
                    au_name = sel[4:]
                    filter_condition |= (df_long["AU_NOME"] == au_name)
            df_long = df_long[filter_condition]

st.write(f"**Dados filtrados:** {len(df_long):,} registros")

st.divider()
st.subheader("📊 Análise Demográfica")

# Seleção do nível de análise
nivel_options = ["Estado (SP)", "Município", "Setor"]

# Adicionar opções de RM/AU se disponíveis nos dados
if 'RM_NOME' in df_long.columns and df_long['RM_NOME'].notna().any():
    nivel_options.append("Região Metropolitana (RM)")
if 'AU_NOME' in df_long.columns and df_long['AU_NOME'].notna().any():
    nivel_options.append("Aglomeração Urbana (AU)")

nivel = st.radio("Nível de análise:", 
                nivel_options,
                horizontal=True, key="nivel_demog")

# Lógica de seleção baseada no nível
if nivel == "Estado (SP)":
    df_analysis = df_long
    title_suffix = "Estado de São Paulo"
        
elif nivel == "Município":
    if all(c in df_long.columns for c in ["CD_MUN", "NM_MUN"]):
        mun_df = df_long[["CD_MUN", "NM_MUN"]].dropna().drop_duplicates().sort_values("NM_MUN")
        if len(mun_df) == 0:
            st.error("❌ Nenhum município disponível nos dados filtrados")
            st.stop()
        mun_options = [f"{row.CD_MUN} — {row.NM_MUN}" for row in mun_df.itertuples(index=False)]
        sel_mun_label = st.selectbox("Selecione o município:", mun_options, key="sel_mun_analysis")
        sel_mun_cod = int(sel_mun_label.split(" — ")[0])
        df_analysis = df_long[df_long["CD_MUN"] == sel_mun_cod]
        title_suffix = sel_mun_label
    else:
        st.error("❌ Colunas de município não disponíveis")
        st.stop()
        
elif nivel == "Setor":
    if all(c in df_long.columns for c in ["CD_MUN", "NM_MUN", "CD_SETOR"]):
        # Primeiro seleciona município
        mun_df = df_long[["CD_MUN", "NM_MUN"]].dropna().drop_duplicates().sort_values("NM_MUN")
        if len(mun_df) == 0:
            st.error("❌ Nenhum município disponível nos dados filtrados")
            st.stop()
        mun_options = [f"{row.CD_MUN} — {row.NM_MUN}" for row in mun_df.itertuples(index=False)]
        sel_mun_label = st.selectbox("Município:", mun_options, key="sel_mun_setor")
        sel_mun_cod = int(sel_mun_label.split(" — ")[0])
        
        # Depois seleciona setor
        setores_df = df_long[df_long["CD_MUN"] == sel_mun_cod]
        setor_options = sorted(setores_df["CD_SETOR"].dropna().unique())
        if len(setor_options) == 0:
            st.error("❌ Nenhum setor disponível para o município selecionado")
            st.stop()
        sel_setor = st.selectbox("Setor:", setor_options, key="sel_setor_analysis")
        df_analysis = df_long[df_long["CD_SETOR"] == sel_setor]
        title_suffix = f"Setor {sel_setor}"
    else:
        st.error("❌ Colunas de setor não disponíveis")
        st.stop()

elif nivel == "Região Metropolitana (RM)":
    if "RM_NOME" in df_long.columns:
        rms_disponiveis = df_long["RM_NOME"].dropna().unique()
        if len(rms_disponiveis) == 0:
            st.error("❌ Nenhuma RM disponível nos dados filtrados")
            st.stop()
        sel_rm = st.selectbox("Selecione a Região Metropolitana:", sorted(rms_disponiveis), key="sel_rm_analysis")
        df_analysis = df_long[df_long["RM_NOME"] == sel_rm]
        title_suffix = f"RM {sel_rm}"
    else:
        st.error("❌ Dados de RM não disponíveis")
        st.stop()

elif nivel == "Aglomeração Urbana (AU)":
    if "AU_NOME" in df_long.columns:
        aus_disponiveis = df_long["AU_NOME"].dropna().unique()
        if len(aus_disponiveis) == 0:
            st.error("❌ Nenhuma AU disponível nos dados filtrados")
            st.stop()
        sel_au = st.selectbox("Selecione a Aglomeração Urbana:", sorted(aus_disponiveis), key="sel_au_analysis")
        df_analysis = df_long[df_long["AU_NOME"] == sel_au]
        title_suffix = f"AU {sel_au}"
    else:
        st.error("❌ Dados de AU não disponíveis")
        st.stop()

else:
    df_analysis = df_long
    title_suffix = "Total filtrado"

# Agregação dos dados para visualização
df_plot = _aggregate_local(df_analysis)

if df_plot.empty:
    st.warning("⚠️ Nenhum dado disponível para os filtros selecionados")
    st.write("DEBUG - Dados de análise:", len(df_analysis))
    if not df_analysis.empty:
        st.write("Colunas disponíveis:", list(df_analysis.columns))
        st.write("Amostra:", df_analysis.head())
    st.stop()

# Layout em colunas para visualizações
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("🔺 Pirâmide Etária")
    try:
        fig = _make_age_pyramid(df_plot.rename(columns={"faixa_etaria":"idade_grupo","populacao":"valor"}), title=f"Demografia — {title_suffix}")
    except Exception:
        fig = go.Figure()
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.subheader("📈 Resumo Populacional")
    total_pop = int(df_plot["populacao"].sum())
    pop_masc = int(df_plot[df_plot["sexo"] == "Masculino"]["populacao"].sum())
    pop_fem = int(df_plot[df_plot["sexo"] == "Feminino"]["populacao"].sum())
    
    st.metric("População Total", f"{total_pop:,}")
    st.metric("População Masculina", f"{pop_masc:,}", f"{pop_masc/total_pop*100:.1f}%")
    st.metric("População Feminina", f"{pop_fem:,}", f"{pop_fem/total_pop*100:.1f}%")
    st.success("✅ Página funcional com agregações e RM/AU via Excel configurado.")

st.divider()
st.subheader("📋 Tabela Demográfica (Padrão ABNT)")

abnt_table = create_abnt_demographic_table(df_plot)

st.dataframe(
    abnt_table,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Faixa Etária": st.column_config.TextColumn("Faixa Etária", width="medium"),
        "Masculino": st.column_config.NumberColumn("Masculino", format="%d"),
        "Feminino": st.column_config.NumberColumn("Feminino", format="%d"),
        "Total": st.column_config.NumberColumn("Total", format="%d"),
        "% Masculino": st.column_config.NumberColumn("% Masculino", format="%.1f%%"),
        "% Feminino": st.column_config.NumberColumn("% Feminino", format="%.1f%%"),
    },
)

csv_abnt = abnt_table.to_csv(index=False, encoding='utf-8-sig')
st.download_button(
    label="📥 Baixar Tabela ABNT (CSV)",
    data=csv_abnt,
    file_name=f"tabela_demografica_abnt_{title_suffix.replace(' ', '_')}.csv",
    mime="text/csv",
)
