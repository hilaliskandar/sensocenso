# Censo 2022 — Plataforma SP (v1.9.3)

Plataforma Streamlit enxuta para análise demográfica (pirâmide etária) por município e por setor censitário, baseada no Parquet local do Censo 2022 de SP.

## Como rodar
```powershell
cd <pasta_do_projeto>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m streamlit run app.py
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

## Algoritmo de ponta a ponta (Demografia)

Esta seção documenta, em detalhes, todas as etapas do pipeline desde as fontes de dados até a apresentação final na página Demografia, incluindo regras de decisão, entradas, saídas e tratamento de bordas.

### Visão geral (fluxo)

```mermaid
flowchart LR
	A[Parquet Censo 2022 - SP (fonte)] --> B[Leitura via DuckDB (UF=35)]
	B --> C[Normalização de colunas\n(aliases + docs/columns_map.csv)]
	C --> D[Decodificação e campos derivados\nCD_SITUACAO→SITUACAO, CD_TIPO→TP_SETOR_TXT]
	D --> E[Enriquecimento RM/AU a partir do Excel\nComposicao_RM_2024.xlsx]
	E --> F[Dataset "wide"]
	F --> G[wide_to_long_pyramid\n(melt das 22 colunas etárias: 11x M/F)]
	G --> H[Normalização de rótulos\nCategorização em 11 faixas (décadas)]
	H --> I[Filtros e escopo escolhidos na UI]
	I --> J[Agregação: sexo × faixa etária]
	J --> K[Padding de faixas faltantes\n+ ordem canônica]
	K --> L1[Gráfico Pirâmide − Município (absoluto)]
	K --> L2[Gráfico Pirâmide − Comparador (% do total do comparador)]
	K --> M[Tabela ABNT\nPivot, totais, % por sexo, % do total, Δ vs comparador]
	L1 --> N[Renderização Plotly + CSS]
	L2 --> N
	M --> O[Export CSV]

	subgraph Comparador
		K1[Determinar comparador]
		K1 -->|1| A1[Se TIPO_RM_AU + NOME_RM_AU disponíveis → usar]
		K1 -->|2| A2[Senão RM_NOME / AU_NOME]
		K1 -->|3| A3[Senão NM_RGI]
		K1 -->|4| A4[Fallback: Estado]
		A1 --> K2[Agrega e normaliza para %]
		A2 --> K2
		A3 --> K2
		A4 --> K2
	end
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
