import sys
from pathlib import Path as _P
import streamlit as st

ROOT = _P(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from censo_app.ui import render_topbar

st.set_page_config(page_title="Sobre — Senso&Censo", layout="wide", initial_sidebar_state="collapsed")
render_topbar(title="Explorador de Dados Censitários", subtitle="Censo 2022 — SP")

st.title("ℹ️ Sobre o Projeto")

st.markdown("""
**Senso&Censo** é uma plataforma de análise e visualização de dados do
Censo Demográfico 2022 (IBGE) para o estado de São Paulo.
Desenvolvida em [Streamlit](https://streamlit.io/), permite explorar pirâmides etárias,
indicadores demográficos e características dos domicílios por município,
setor censitário e recortes regionais (RM, AU, Regiões Intermediárias e Imediatas).
""")

st.divider()

# ---- Recursos ---------------------------------------------------------------
st.subheader("📋 Funcionalidades")

col1, col2 = st.columns(2)
with col1:
    st.markdown("""
**🏛️ Demografia**
- Pirâmide etária por município, setor, RM/AU, região ou estado
- Comparador automático (RM/AU → Região Imediata → Estado)
- Tabela ABNT com % e Δ pontos percentuais vs comparador
- Download CSV
- Resumo populacional (M/F, totais)

**📊 Indicadores**
- Razões de dependência (total, jovem, idosa)
- Índices de envelhecimento
- Old Age Dependency Ratio (OADR) e Potential Support Ratio (PSR)
- Proxy de taxa bruta de natalidade
- Flags de qualidade (denominador pequeno, age heaping)
""")
with col2:
    st.markdown("""
**🏠 Domicílios**
- Indicadores categóricos: tipo, espécie, abastecimento de água,
  esgoto, lixo, banheiros, crianças
- Comparação Estado SP vs escopo selecionado
- Gráficos de pizza e barras

**⚙️ Infraestrutura**
- Leitura de Parquet local via DuckDB (zero cópia em memória)
- Enriquecimento RM/AU via Excel oficial (2024)
- Cache TTL (1 hora) para recarregamento automático
- Keepalive opcional para evitar expiração de sessão
""")

st.divider()

# ---- Dados ------------------------------------------------------------------
st.subheader("📂 Dados e Fontes")

st.markdown("""
| Insumo | Descrição | Fonte |
|--------|-----------|-------|
| Parquet SP 2022 | Tabelas agregadas por setor censitário — UF 35 | IBGE — Censo 2022 |
| `Composicao_RM_2024.xlsx` | Composição oficial de RM e AU | IBGE — 2024 |
| `docs/columns_map.csv` | Mapeamento parquet → colunas canônicas do app | Elaboração própria |

**Variáveis principais utilizadas:**
- `V0001` — Total de pessoas residentes
- `V0002` a `V0007` — Totais de domicílios (particulares, coletivos, médias)
- Colunas de sexo × faixa etária (11 grupos × 2 sexos = 22 colunas)
- `CD_SITUACAO` / `SITUACAO` — Situação urbana/rural do setor
- `CD_TIPO` / `TP_SETOR_TXT` — Tipo de setor (favela, quartel, indígena, etc.)
- `RM_NOME` / `AU_NOME` — Região Metropolitana / Aglomeração Urbana
- `NM_RGINT` / `NM_RGI` — Região Geográfica Intermediária / Imediata
""")

st.divider()

# ---- Metodologia ------------------------------------------------------------
st.subheader("🔬 Metodologia")

with st.expander("Faixas etárias canônicas (11 grupos)"):
    st.markdown("""
O app adota **11 grupos** de décadas, construídos por soma direta das faixas publicadas pelo IBGE,
sem redistribuição proporcional nem suposições:

| # | Faixa | | # | Faixa |
|---|-------|-|---|-------|
| 1 | 0 a 4 anos  | | 7 | 30 a 39 anos |
| 2 | 5 a 9 anos  | | 8 | 40 a 49 anos |
| 3 | 10 a 14 anos| | 9 | 50 a 59 anos |
| 4 | 15 a 19 anos| |10 | 60 a 69 anos |
| 5 | 20 a 24 anos| |11 | 70 anos ou mais |
| 6 | 25 a 29 anos| | | |

Categorias ausentes nos dados são exibidas com valor 0 para manter a mesma altura visual
entre as pirâmides do escopo e do comparador.
""")

with st.expander("Comparador demográfico"):
    st.markdown("""
O comparador é selecionado automaticamente na seguinte ordem de prioridade:

1. `TIPO_RM_AU` + `NOME_RM_AU` — Região Metropolitana ou Aglomeração Urbana unificada
2. `RM_NOME` ou `AU_NOME` — RM/AU pelo caminho legado
3. `NM_RGI` — Região Geográfica Imediata (IBGE 2017)
4. Estado de São Paulo (fallback)

O comparador é sempre exibido em **% do total do comparador** (estrutura etária relativa),
enquanto o município/escopo permanece em **valores absolutos**.
""")

with st.expander("Indicadores demográficos calculados"):
    st.markdown(r"""
| Sigla | Nome | Fórmula |
|-------|------|---------|
| RDT | Razão de Dependência Total | $(P_{0-14} + P_{65+}) / P_{15-64} \times 100$ |
| RDJ | Razão de Dependência Jovem | $P_{0-14} / P_{15-64} \times 100$ |
| RDI | Razão de Dependência de Idosos | $P_{65+} / P_{15-64} \times 100$ |
| OADR | Old Age Dependency Ratio | $P_{65+} / P_{20-64} \times 100$ |
| PSR | Potential Support Ratio | $P_{20-64} / P_{65+}$ |
| IE₆₀ | Índice de Envelhecimento 60+ | $P_{60+} / P_{0-14} \times 100$ |
| IE₆₅ | Índice de Envelhecimento 65+ | $P_{65+} / P_{0-14} \times 100$ |
| Prop₈₀ | Proporção 80+ | $P_{80+} / P_{total} \times 100$ |
| TBN* | Tx. Bruta Natalidade (proxy) | $P_0 / P_{total} \times 1000$ |

*Proxy — idade 0 como indicativo de nascimentos recentes; não é taxa real de natalidade.
""")

st.divider()

# ---- Stack tecnológica -------------------------------------------------------
st.subheader("🛠️ Tecnologias")

st.markdown("""
| Componente | Biblioteca |
|------------|-----------|
| Interface web | [Streamlit](https://streamlit.io/) ≥ 1.36 |
| Manipulação de dados | [pandas](https://pandas.pydata.org/) ≥ 2.1 |
| Leitura de Parquet | [DuckDB](https://duckdb.org/) ≥ 1.0 |
| Visualização | [Plotly](https://plotly.com/python/) ≥ 5.20 |
| Excel RM/AU | [openpyxl](https://openpyxl.readthedocs.io/) ≥ 3.1 |
| Aritmética | [NumPy](https://numpy.org/) ≥ 1.26 |
| Keepalive | [streamlit-autorefresh](https://github.com/kmcgrady/streamlit-autorefresh) ≥ 1.0 |
""")

st.divider()

# ---- Limitações e notas -------------------------------------------------------
st.subheader("⚠️ Limitações e Notas")

st.markdown("""
- **Unidade territorial base 2022**: alterações de limites municipais entre censos podem afetar
  comparações temporais; o app não faz compatibilização histórica.
- **Pequenas diferenças de totais**: arredondamentos e ausências pontuais em setores muito pequenos
  podem gerar discrepâncias de 1–2 pessoas entre a soma de faixas e `V0001`.
  Não há reponderação; a diferença é reportada na página de Domicílios.
- **Percentuais do comparador**: sempre relativos ao total do comparador (estrutura etária).
  Interpretar com cautela em populações muito pequenas (< 500 pessoas na faixa produtiva).
- **TBN proxy**: a contagem de crianças com 0 anos de idade é apenas um indicativo, não uma
  taxa de natalidade calculada com o método demográfico padrão.
- **Sem SIDRA online**: o app usa dados locais (Parquet); a integração com a API SIDRA está
  disponível no módulo `src/censo_app/sidra.py` mas não é utilizada na interface principal.
""")

st.divider()

# ---- Referências --------------------------------------------------------------
st.subheader("📚 Referências")

st.markdown("""
- IBGE. **Censo Demográfico 2022**. Disponível em: <https://www.ibge.gov.br/estatisticas/sociais/populacao/22827-censo-demografico-2022.html?=&t=downloads>
- IBGE. **Regiões Geográficas Imediatas e Intermediárias 2017**. Disponível em: <https://www.ibge.gov.br/geociencias/organizacao-do-territorio/divisao-regional/15778-regioes-geograficas.html>
- IBGE. **Composição das Regiões Metropolitanas e Aglomerações Urbanas 2024**. Arquivo local: `insumos/Composicao_RM_2024.xlsx`
- UNFPA / ABEP. **Indicadores Demográficos** — metodologias de razões de dependência e índices de envelhecimento.
- Documentação local: `docs/Guia_Indicadores_Demograficos_IBGE2022.xlsx` · `docs/Documentacao_Avancada_Indicadores.md`
""")

st.divider()
st.caption("Senso&Censo · Censo Demográfico 2022 — IBGE · São Paulo")
