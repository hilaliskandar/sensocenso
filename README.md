# Censo 2022 — Plataforma SP (v1.9.3)

Plataforma Streamlit enxuta para análise demográfica (pirâmide etária) por município e por setor censitário, baseada no Parquet local do Censo 2022 de SP.

## Sumário / Table of Contents

- Idioma / Language: [Português](#censo-2022--plataforma-sp-v193) · [English](#censo-2022--sp-platform-english)
- [Como rodar (Windows/PowerShell)](#como-rodar-windowspowershell)
- [Parquet esperado](#parquet-esperado)
- [Recursos](#recursos)
- [Erros comuns (Windows)](#erros-comuns-windows)
- [Algoritmo de ponta a ponta (Demografia)](#algoritmo-de-ponta-a-ponta-demografia)
	- [Visão geral (fluxo)](#visão-geral-fluxo)
	- [Segundo diagrama — Tabela ABNT](#segundo-diagrama--tabela-abnt-pipeline-e-cálculos)
- [Censo 2022 — SP Platform (English)](#censo-2022--sp-platform-english)
	- [How to run (Windows/PowerShell)](#how-to-run-windowspowershell)
	- [Common issues (Windows)](#common-issues-windows)
	- [End-to-end algorithm (Demography)](#end-to-end-algorithm-demography)

## Como rodar (Windows/PowerShell)

1) Pré-requisitos
- Python 3.10+ (ou Conda/Miniconda)
- Parquet do Censo SP e Excel de RM/AU disponíveis no disco

2) Configure caminhos em `config/settings.yaml`
```yaml
paths:
	parquet_default: "D:/repo/saida_parquet/base_integrada_final.parquet"
	rm_au_excel_default: "D:/repo/insumos/Composicao_RM_2024.xlsx"
```

3) Ambiente e dependências (opção A: venv)
```powershell
cd <pasta_do_projeto>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3') Ambiente (opção B: Conda)
```powershell
conda create -y -n sensocenso python=3.11
conda activate sensocenso
pip install -r requirements.txt
```

4) Executar o app
```powershell
python -m streamlit run app.py --server.port 8501
```

No app, abra a página **Demografia (10_Demografia)**.

## Parquet esperado
Atualize o campo no topo da página, por padrão:
```
D:\repo\saida_parquet\base_integrada_final.parquet
```

## Recursos
- Seleção de município e de setor.
- Filtros: **SITUACAO** (Urbana/Rural), **CD_SITUACAO** (decodificado) e **CD_TIPO** (decodificado).
- Pirâmide etária (M/F, 11 faixas).
- Checagem: soma M+F vs **V0001 (Total de pessoas)**, diferença absoluta e %.
- Gráfico de pizza (M/F) para setor e para município.
- Cache de dados com TTL e keepalive opcional.

### Erros comuns (Windows)
- Porta ocupada: troque `--server.port 8501` para outro (8502, 8511, …).
- Processos travados: finalize Python.
	```powershell
	taskkill /f /im python.exe 2>$null
	```
- Dados não carregam: verifique caminhos no `settings.yaml` e se o Parquet/Excel existem.

## Algoritmo de ponta a ponta (Demografia)

Esta seção documenta, em detalhes, todas as etapas do pipeline desde as fontes de dados até a apresentação final na página Demografia, incluindo regras de decisão, entradas, saídas e tratamento de bordas.

### Visão geral (fluxo)

```mermaid
flowchart LR
	A[Parquet Censo 2022 - SP (fonte)] --> B[Leitura via DuckDB (UF=35)]
	B --> C[Normalização de colunas<br/>(aliases + docs/columns_map.csv)]
	C --> D[Decodificação e campos derivados<br/>CD_SITUACAO para SITUACAO, CD_TIPO para TP_SETOR_TXT]
	D --> E[Enriquecimento RM/AU a partir do Excel<br/>Composicao_RM_2024.xlsx]
	E --> F[Dataset "wide"]
	F --> G[wide_to_long_pyramid<br/>(melt das 22 colunas etárias: 11x M/F)]
	G --> H[Normalização de rótulos<br/>Categorização em 11 faixas (décadas)]
	H --> I[Filtros e escopo escolhidos na UI]
	I --> J[Agregação: sexo x faixa etária]
	J --> K[Padding de faixas faltantes<br/>+ ordem canônica]
	K --> L1[Gráfico Pirâmide - Município (absoluto)]
	K --> L2[Gráfico Pirâmide - Comparador (% do total do comparador)]
	K --> M[Tabela ABNT<br/>Pivot, totais, % por sexo, % do total, Delta vs comparador]
	L1 --> N[Renderização Plotly + CSS]
	L2 --> N
	M --> O[Export CSV]

	subgraph Comparador
		K1[Determinar comparador]
		K1 -->|1| A1[Se TIPO_RM_AU + NOME_RM_AU disponíveis, usar]
		K1 -->|2| A2[Se não, RM_NOME / AU_NOME]
		K1 -->|3| A3[Se não, NM_RGI]
		K1 -->|4| A4[Fallback: Estado]
		A1 --> K2[Agrega e normaliza para %]
		A2 --> K2
		A3 --> K2
		A4 --> K2
	end
```

### Segundo diagrama — Tabela ABNT (pipeline e cálculos)

```mermaid
flowchart TD
	L[df_plot (sexo x faixa)] --> P1[Pivot por faixa: colunas Masculino/Feminino]
	P1 --> T1[Total = Masculino + Feminino]
	T1 --> PM[% Masculino = M/Total * 100]
	T1 --> PF[% Feminino = F/Total * 100]
	T1 --> PT[% do Total (escopo) por faixa]
	subgraph Comparador
		LC[df_comp_plot] --> PC1[Pivot comparador]
		PC1 --> TC1[Total_comp]
		TC1 --> PTC[% do Total (Comp) por faixa]
	end
	PT --> MRG[Merge PT x PTC por faixa]
	PTC --> MRG
	MRG --> D[Delta vs Comp. = PT - PTC (pp)]
	D --> O1[Ordenação canônica das faixas + linha TOTAL]
	O1 --> O2[Formatar e renderizar HTML ABNT]
	O2 --> CSV[Export CSV UTF-8 BOM]
```

### Entradas
- Caminho do Parquet (SP/UF=35): `config.paths.parquet_default` ou informado no app.
- Excel com composição RM/AU: `config.paths.rm_au_excel_default` (aba RM e AU), usado para mapear CD_MUN → RM_NOME/AU_NOME.
- Configurações de página (quando disponíveis): `get_page_config('demografia')`, incluindo `age_buckets_order`.

### Saídas
- Dois gráficos de pirâmide etária (Plotly):
	- Município/escopo em valores absolutos.
	- Comparador em porcentagem (% do total do comparador).
- Tabela em padrão ABNT: Masculino | Feminino | Total | % Masculino | % Feminino | % do Total | Δ vs Comp.
- Download CSV da tabela.

### Regras e decisões principais
- Faixas etárias canônicas: exatamente 11 grupos (décadas):
	0–4, 5–9, 10–14, 15–19, 20–24, 25–29, 30–39, 40–49, 50–59, 60–69, 70+.
- Sem redistribuição de dados entre faixas (sem suposições); faixas ausentes são exibidas com zero após padding para manter a mesma altura entre gráficos.
- Comparador sempre em % do próprio total; o município/escopo fica em absoluto.
- Ordenação de categorias do eixo Y forçada para manter alinhamento entre os gráficos.
- Tabela ABNT inclui % do total do escopo e do comparador e o delta (pontos percentuais) por faixa etária.

### Etapas detalhadas
1) Leitura e normalização (módulo `src/censo_app/transform.py`)
	 - DuckDB lê o Parquet e filtra UF=35 (SP).
	 - Normalização de colunas:
		 - Mapeamento externo opcional `docs/columns_map.csv` (parquet_column → app_equivalent).
		 - Aliases semânticos (ex.: `CD_SETOR`, `CD_MUN`, `NM_MUN`, `CD_SITUACAO`, `CD_TIPO`, `RM_NOME`, `AU_NOME`, `NM_RGINT`, `NM_RGI`).
		 - Variáveis V0001–V0007 padronizadas para maiúsculas.
	 - Decodificação/derivação:
		 - `SITUACAO` (Urbana/Rural) a partir de `CD_SITUACAO` ou texto detalhado.
		 - `TP_SETOR_TXT` a partir de `CD_TIPO` (e vice-versa quando possível).
	 - Enriquecimento RM/AU a partir do Excel:
		 - Abas preferenciais: “Composição - Recortes Metropoli” (RM) e “Composição - Aglomerações Urban” (AU).
		 - Campos: `COD_MUN`, `NOME_CATMETROPOL`, `SIGLA_UF` (filtra `SP`).
		 - Produz `RM_NOME` e/ou `AU_NOME` e campos auxiliares: `REGIAO_RM_AU`, `TIPO_RM_AU` (prioriza RM), `NOME_RM_AU`.
	 - Saída: dataframe “wide” (`df_wide`).

2) Conversão wide → long (função `wide_to_long_pyramid`)
	 - Seleciona exatamente 11 colunas por sexo (22 no total) com regex dos rótulos etários.
	 - `melt` para colunas: `idade_grupo` (categórica com as 11 faixas), `sexo`, `valor`.
	 - Preserva chaves geográficas e de contexto quando disponíveis: `CD_SETOR`, `CD_MUN`, `NM_MUN`, `CD_UF`, `NM_UF`, `CD_SITUACAO`, `SITUACAO`, `SITUACAO_DET_TXT`, `CD_TIPO`, `TP_SETOR_TXT`, `V0001`, `RM_NOME`, `AU_NOME`, `NM_RGINT`, `NM_RGI`.

3) Filtros e escopo na UI (arquivo `pages/10_Demografia.py`)
	 - Filtros principais: `SITUACAO` (padrão: Urbana), `CD_TIPO` (padrão: 0 e 1), RM/AU (se houver), além da seleção de escala: Estado, RM/AU, Região Intermediária, Região Imediata, Município, Setores.
	 - Seleção do escopo aplica recortes sobre `df_long`.

4) Agregação e padding
	 - Agrega por `sexo` × `faixa_etaria` no escopo escolhido.
	 - Normaliza rótulos de faixa e aplica padding para garantir presença das 11 categorias para ambos os sexos (valores 0 onde necessário).
	 - Ordenação do eixo Y forçada com a lista canônica de faixas.

5) Comparador (prioridade)
	 - Ordem: (1) `TIPO_RM_AU`+`NOME_RM_AU`; (2) `RM_NOME`/`AU_NOME`; (3) `NM_RGI`; (4) Estado.
	 - Agrega e converte valores para % do total do comparador.

6) Visualização (módulo `src/censo_app/viz.py`)
	 - Gráficos Plotly com barras horizontais espelhadas (Masculino negativo, Feminino positivo).
	 - Município/escopo em valores absolutos; comparador em % (eixo X com sufixo `%`).
	 - Oculta legendas/títulos supérfluos e usa layout compacto; CSS reduz margens/gaps.

7) Tabela ABNT
	 - Pivot por faixa e sexo; calcula `Total`, `% Masculino`, `% Feminino`.
	 - Calcula `% do Total` (escopo) e `% do Total (Comp)` e o delta `Δ vs Comp.` em pontos percentuais.
	 - Ordena faixas conforme ordem canônica; adiciona linha `TOTAL`.
	 - Exporta CSV (UTF-8 com BOM).

### Como usar no app
- Escolha a escala (Estado, RM/AU, Região, Município, Setores).
- Ajuste filtros Situação (U/R) e Tipo de Setor conforme necessário.
- Na escala Município, o comparador é determinado automaticamente (RM/AU > RM/AU legado > RGI > Estado).
- Baixe a tabela em CSV pelo botão “Baixar Tabela (CSV)”.

---

# Censo 2022 — SP Platform (English)

Streamlit app for demographic analysis (age pyramid) by municipality and census tract, based on local SP 2022 Census Parquet.

## How to run (Windows/PowerShell)

1) Prerequisites
- Python 3.10+ (or Conda/Miniconda)
- Local Census Parquet and RM/AU Excel files

2) Set paths in `config/settings.yaml`
```yaml
paths:
	parquet_default: "D:/repo/saida_parquet/base_integrada_final.parquet"
	rm_au_excel_default: "D:/repo/insumos/Composicao_RM_2024.xlsx"
```

3) Environment (option A: venv)
```powershell
cd <project_folder>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3') Environment (option B: Conda)
```powershell
conda create -y -n sensocenso python=3.11
conda activate sensocenso
pip install -r requirements.txt
```

4) Run
```powershell
python -m streamlit run app.py --server.port 8501
```

Open page: Demografia (10_Demografia).

### Common issues (Windows)
- Busy port: change `--server.port 8501`.
- Stuck processes: kill Python.
	```powershell
	taskkill /f /im python.exe 2>$null
	```
- Data not loading: ensure paths in `settings.yaml` and files exist.

## End-to-end algorithm (Demography)

```mermaid
flowchart LR
	A[SP Census 2022 Parquet (source)] --> B[Read via DuckDB (UF=35)]
	B --> C[Column normalization<br/>(aliases + docs/columns_map.csv)]
	C --> D[Decoding and derived fields<br/>CD_SITUACAO to SITUACAO, CD_TIPO to TP_SETOR_TXT]
	D --> E[RM/AU enrichment from Excel<br/>Composicao_RM_2024.xlsx]
	E --> F[Wide dataset]
	F --> G[wide_to_long_pyramid<br/>(melt 22 age-sex cols: 11x M/F)]
	G --> H[Label normalization<br/>11 decade buckets]
	H --> I[UI filters and scope]
	I --> J[Aggregation: sex x age bucket]
	J --> K[Pad missing buckets<br/>+ canonical order]
	K --> L1[Pyramid - Scope (absolute)]
	K --> L2[Pyramid - Comparator (% of comparator total)]
	K --> M[ABNT table<br/>Pivot, totals, % by sex, % of total, Delta vs comparator]
	L1 --> N[Plotly + CSS]
	L2 --> N
	M --> O[Export CSV]

	subgraph Comparator
		K1[Pick comparator]
		K1 -->|1| A1[If TIPO_RM_AU + NOME_RM_AU available, use]
		K1 -->|2| A2[Else RM_NOME / AU_NOME]
		K1 -->|3| A3[Else NM_RGI]
		K1 -->|4| A4[Fallback: State]
		A1 --> K2[Aggregate and normalize to %]
		A2 --> K2
		A3 --> K2
		A4 --> K2
	end
```

```mermaid
flowchart TD
	L[df_plot (sex x age)] --> P1[Pivot by age: columns Male/Female]
	P1 --> T1[Total = Male + Female]
	T1 --> PM[% Male = M/Total * 100]
	T1 --> PF[% Female = F/Total * 100]
	T1 --> PT[% of Total (scope) by age]
	subgraph Comparator
		LC[df_comp_plot] --> PC1[Comparator pivot]
		PC1 --> TC1[Total_comp]
		TC1 --> PTC[% of Total (Comp) by age]
	end
	PT --> MRG[Merge PT x PTC by age]
	PTC --> MRG
	MRG --> D[Delta vs Comp. = PT - PTC (pp)]
	D --> O1[Canonical order + TOTAL row]
	O1 --> O2[Format + render ABNT HTML]
	O2 --> CSV[Export CSV UTF-8 BOM]
```

### Esquemas de dados esperados
- Wide (parcial, depende do Parquet):
	- Chaves/contexto: `CD_SETOR`, `CD_MUN`, `NM_MUN`, `CD_UF`, `NM_UF`, `CD_SITUACAO`, `SITUACAO`/`SITUACAO_DET_TXT`, `CD_TIPO`/`TP_SETOR_TXT`, `RM_NOME`, `AU_NOME`, `NM_RGINT`, `NM_RGI`, `V0001`.
	- Idade/sexo (22 colunas): “Sexo masculino, <faixa>”, “Sexo feminino, <faixa>” nas 11 faixas canônicas.
- Long (`df_long`): `idade_grupo` (categórica nas 11 faixas), `sexo` (Masculino/Feminino), `valor` (int), + chaves/contexto quando disponíveis.

### Tratamento de erros e bordas
- Colunas etárias não encontradas: a conversão wide→long lança erro explicativo.
- Excel RM/AU ausente ou diferente: tenta heurísticas; se falhar, segue sem RM/AU (comparador cai para alternativas).
- Totais zero no comparador: percentuais são 0 para evitar divisão por zero.
- Filtros sem resultados: a página avisa e interrompe a renderização.

### Referências de implementação
- `src/censo_app/transform.py`: leitura, normalização, decodificação, RM/AU, wide→long, agregação.
- `src/censo_app/viz.py`: pirâmide etária (Plotly), ordem de categorias.
- `pages/10_Demografia.py`: UI, filtros, comparador, padding, tabela ABNT, layout/CSS.
