import sys
from pathlib import Path
import streamlit as st

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

st.set_page_config(page_title="SensoCenso — Demografia v2.0", layout="wide")
st.title("🏛️ SensoCenso — Análise Demográfica Avançada v2.0")

st.markdown("""
## Bem-vindo ao SensoCenso

Esta plataforma oferece análise demográfica avançada baseada nos dados do Censo 2022 do IBGE, 
com funcionalidades aprimoradas para estudos populacionais e planejamento urbano.

### 📊 Funcionalidades Principais

**🔸 Demografia (Recomendado)**
- Análise populacional multi-nível (Estado → Setor)
- Indicadores demográficos avançados (RDT, RDJ, RDI, IE, etc.)
- Integração automática de Regiões Metropolitanas/Aglomerações Urbanas
- Filtros inteligentes com padrões otimizados
- Exportação de dados e indicadores

**🔸 Pirâmides Etárias**
- Visualizações interativas de estrutura populacional
- Comparações entre diferentes níveis geográficos
- Análise de setores censitários específicos

**🔸 Ferramentas de Apoio**
- Listagem de setores por município
- Busca e documentação técnica
- Schema de dados e validação

### 🚀 Como Começar

1. **Acesse a página Demografia** no menu lateral para análise completa
2. Configure sua fonte de dados (Parquet local)
3. Aplique filtros conforme sua análise
4. Explore indicadores e visualizações
5. Exporte resultados quando necessário

### 📖 Documentação

- **[Documentação Avançada](docs/Documentacao_Avancada_Indicadores.md)**: Metodologia e implementação
- **[Guia de Indicadores](docs/Guia_Indicadores_Demograficos_IBGE2022.xlsx)**: Referência técnica completa
- **Página Sobre**: Links úteis e notas metodológicas do IBGE

---
*Versão 2.0 - Funcionalidade dual-source com indicadores demográficos avançados*
""")

st.sidebar.success("✅ Selecione uma página no menu acima para começar")
