# TIC–TIM — Pipeline reprodutível de demografia, habitação e entorno urbano

Este subprojeto reconstrói, de forma reprodutível, o fluxo analítico utilizado no diagnóstico regional TIC–TIM: obtenção das fontes oficiais, harmonização 2000–2010–2022, preparação dos agregados setoriais do Censo 2022, cálculo dos indicadores, territorialização das quatro famílias analíticas, testes de sensibilidade e autocorrelação espacial, sínteses municipais e geração das tabelas e mapas utilizados no relatório.

## Estado

- Relatório regional: redação encerrada e em revisão humana.
- Caderno metodológico público: versão conceitualmente estabilizada.
- Pipeline longitudinal: etapas 00, 01, 02a, 02b e 02c implementadas e validadas em execução viva contra fontes públicas.
- A etapa 02b reconstruiu 60 linhas (30 municípios × 2000/2010), sem nulos nas três bandas etárias, e passou o gate de regressão com zero divergência nas 20 chaves sentinela.
- A etapa 02c fechou a matriz 30 × 3: 90 linhas, 30 municípios e 2000/2010/2022. Para 2022, o universo é `SITUACAO=Urbana`; as bandas etárias usam somente setores em que V01031–V01041 estão simultaneamente divulgadas. A regressão contra dez sentinelas auditadas resultou em zero divergências.
- Etapa 03a implementada: congela os descritores SIDRA 156 e 185, resolve semanticamente situação do domicílio e número de moradores e identifica, no índice oficial congelado do Censo 2022, os arquivos `Básico` e `Características do domicílio 1`. Nenhum indicador domiciliar é calculado enquanto variáveis e denominadores ainda forem ambíguos.

## Princípios de reprodução

1. Usar somente fontes públicas e versões explicitamente registradas.
2. Preservar numeradores, denominadores, categorias originais e flags de cobertura antes de derivar indicadores.
3. Não converter ausência, supressão, sigilo ou não aplicabilidade em zero.
4. Não reconstruir por diferença valores omitidos pelo provedor para proteção estatística.
5. Manter separadas as escalas municipal, setorial, moradores, domicílios e faces de logradouro.
6. Tratar variáveis municipais propagadas aos setores apenas como contexto compartilhado, nunca como observação microlocal.
7. Registrar parâmetros e universos efetivos de cada etapa.
8. Produzir artefatos intermediários auditáveis e hashes quando aplicável.
9. Reproduzir os elementos visuais a partir das bases analíticas, e não a partir de imagens finais.
10. Não depender de Google Drive, nomes de usuário ou caminhos particulares de máquina.
11. Usar produtos históricos auditados somente como oráculos de QA, nunca como entrada para reconstruir os resultados.

## Estrutura do código

```text
subprojetos/tic_tim_demografia_habitacao/
├── README.md
├── pyproject.toml
├── config/
│   ├── municipios.yml
│   ├── fontes.yml
│   ├── paths.yml
│   └── parametros.yml
├── src/tic_tim_demografia/
│   ├── config.py
│   ├── paths.py
│   ├── proveniencia.py
│   ├── etapa00.py
│   ├── etapa01.py
│   ├── etapa02.py
│   ├── etapa02b.py
│   ├── etapa02c.py
│   ├── etapa03a.py
│   ├── fontes/
│   ├── harmonizacao/
│   └── qa/
├── scripts/
│   └── run_pipeline.py
├── tests/
│   └── fixtures/
└── docs/
```

Os dados e resultados não são versionados. Por padrão ficam em `data/`; a variável `TIC_TIM_DATA_ROOT` permite direcionar o armazenamento para qualquer diretório ou volume externo. Consulte `docs/ARQUITETURA_DADOS.md`.

## Execução inicial

Instalação em ambiente limpo:

```bash
cd subprojetos/tic_tim_demografia_habitacao
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
python scripts/run_pipeline.py --etapa 00
python scripts/run_pipeline.py --etapa 01
python scripts/run_pipeline.py --etapa 02a
python scripts/run_pipeline.py --etapa 02b
python scripts/run_pipeline.py --etapa 02c
python scripts/run_pipeline.py --etapa 03a
```

Para externalizar o armazenamento:

```bash
export TIC_TIM_DATA_ROOT=/dados/tic_tim_demografia
python scripts/run_pipeline.py --etapa implementadas
```

A etapa 01 congela os descritores SIDRA das tabelas 1518, 3107, 156 e 185 e snapshots dos índices públicos do IBGE para agregados setoriais 2022, características urbanísticas do entorno, FCU e CNEFE. Esses snapshots documentam exatamente o catálogo disponível na execução antes que arquivos específicos sejam selecionados e baixados.

## Etapas do pipeline

### 00. Configuração e manifesto de execução

Define os 30 municípios, anos censitários, versões das fontes, diretórios, parâmetros estatísticos, percentis e projeções cartográficas. Valida códigos IBGE, coroas e exclusões antes de qualquer aquisição.

### 01. Aquisição das fontes

Baixa/congela descritores SIDRA e índices de publicação do IBGE. Cada aquisição registra URL final, data, tamanho e SHA-256. Arquivos em `raw/` não são substituídos silenciosamente.

### 02a. Gate semântico SIDRA

Lê os descritores oficiais e seleciona uma partição etária mutuamente exclusiva de 21 classes: quinquênios de 0–4 até 95–99 e 100 anos ou mais. Isso evita dupla contagem entre faixas agregadas e idades simples presentes simultaneamente nos descritores das tabelas 1518 e 3107. As 21 classes são então agregadas em 0–14, 15–59 e 60+ sem interpolação.

### 02b. Harmonização longitudinal 2000–2010

Baixa os 30 municípios em lotes auditáveis, preserva as respostas JSON brutas e gera `processed/municipal/base_longitudinal_2000_2010.parquet` e `.csv`. O sinal convencional `-` do SIDRA é interpretado como zero segundo as convenções tabulares do IBGE; outros sinais permanecem bloqueadores.

A execução viva fechou 60 linhas, 30 municípios, dois anos, zero nulos nas três bandas e zero divergências no oráculo de regressão de 10 municípios × 2 anos.

### 02c. Incorporação de 2022

Identifica os arquivos `Básico` e `Demografia` no índice oficial congelado e seleciona `SITUACAO=Urbana`. As três bandas são calculadas somente sobre setores em que V01031–V01041 estão simultaneamente divulgadas. `x/X` permanece ausente: não é zero, não é imputado e não é reconstruído por diferença.

Na execução viva de fechamento foram observados 9.087 setores urbanos no `Básico`, 8.920 com linha no arquivo de demografia e 8.274 com estrutura etária completa. A cobertura setorial municipal da estrutura etária variou de 75,0% a aproximadamente 96,35%. Nos setores em que V01006 e todas as classes são públicas, o fechamento interno teve diferença máxima absoluta zero. A matriz final contém 90 linhas e o gate de regressão de 2022 apresentou zero divergências nas dez sentinelas.

Produtos principais:

- `processed/municipal/base_longitudinal_2000_2010_2022.parquet`;
- `processed/municipal/base_longitudinal_2000_2010_2022.csv`;
- `outputs/qa/etapa02c_cobertura_idade_2022.csv`;
- `outputs/qa/etapa02c_harmonizacao_2022_urbano.json`.

### 03a. Gate semântico e descoberta das fontes domiciliares

Prepara a reprodução dos indicadores de domicílios sem reutilizar as planilhas históricas como fonte de cálculo. A etapa 01 congela os descritores das tabelas SIDRA 156 e 185. A 03a resolve semanticamente a situação do domicílio, identifica estruturalmente a dimensão de número de moradores quando o rótulo variar e localiza no catálogo 2022 os arquivos `Básico` e `Características do domicílio 1`.

A etapa termina deliberadamente antes do cálculo e grava `outputs/qa/etapa03a_selecao_fontes_domicilios.json`. Permanecem como gates para a 03b: resolver as variáveis/medidas da tabela 156; confirmar o denominador da participação de unipessoais; resolver V00017–V00026 e seu universo no dicionário 2022; e confirmar a fonte exata do tamanho médio domiciliar de 2022.

### 03b. Formação e transformação do estoque domiciliar ocupado

Pendente. Deverá reproduzir DPO, crescimento de DPO, divergência entre crescimento domiciliar e populacional, tamanho médio e domicílios unipessoais em 2000, 2010 e 2022. Não poderá substituir o universo domiciliar próprio pela população urbana da etapa 02c sem demonstração de equivalência.

### 04. Renovação demográfica recente

Calcula a razão criança–mulher (0–4 / mulheres 15–49 × 1.000), preservando a interpretação como proxy censitária de renovação demográfica recente, e não como taxa de fecundidade ou natalidade.

### 05. Privação sanitário-ambiental censitariamente observável

Reconstrói os domínios de água, esgotamento, resíduos e a proxy censitária de drenagem baseada na presença/ausência de bueiro ou boca de lobo; calcula o ISAU e a privação `1 - ISAU`, com os mesmos critérios de cobertura do fechamento analítico.

### 06. Ausência de atributos selecionados do entorno urbano

Calcula os cinco componentes utilizados na família F3: drenagem/bueiro, calçada, pavimentação, iluminação e arborização. A regra final identifica a família quando pelo menos dois dos cinco sinais estão relativamente elevados segundo o corte adotado.

### 07. Quatro famílias analíticas

Reconstrói F1 dinâmica do estoque domiciliar ocupado e renovação demográfica recente; F2 privação sanitário-ambiental censitariamente observável; F3 ausência de atributos selecionados do entorno urbano; e F4 estrutura etária e arranjos domiciliares. A convergência multidimensional corresponde à presença de três ou quatro famílias, sem interpretação automática como déficit, severidade ou prioridade.

### 08. Cortes relativos e sensibilidade

Calcula P75 como referência principal e P80 como teste de estabilidade. Variáveis cujo percentil seja zero seguem a regra específica documentada no caderno metodológico, evitando que valor zero seja classificado como carência elevada.

### 09. Validação espacial

Constrói vizinhança Queen sobre a malha censitária, identifica ilhas, reproduz o Moran global com o número de permutações definido na configuração e registra o universo efetivamente utilizado.

### 10. Comparações municipais

Produz sínteses municipais, correlações de Spearman e os indicadores comparativos usados no panorama regional, mantendo separadas medidas municipais relativas das quatro famílias da territorialização.

### 11. Produtos tabulares e cartográficos

Gera automaticamente tabelas de síntese, matrizes municipais, arquivos geoespaciais e mapas em padrão editorial definido, incluindo mapas regionais, mapas setoriais e pranchas multipainel do entorno.

### 12. QA e reprodutibilidade

Executa testes de unicidade de chaves, universos, denominadores, faixas válidas, cobertura espacial, equivalência de agregações, estabilidade P75/P80 e regressão contra valores auditados.

## Gate de regressão histórico

A v0.16 auditada estabeleceu a referência de fechamento da série: 30/30 municípios completos nos três censos, 630 registros de faixas etárias em 2000, 630 em 2010, Santo Antônio de Posse fechado em 20.650 habitantes em 2010 e correção material de Jundiaí documentada. Esses fatos orientam os testes, mas o novo pipeline precisa reencontrar os valores a partir das fontes oficiais.

Os fixtures atuais usam dez municípios sentinela × dois anos para 2000/2010 e dez sentinelas para o painel urbano de 2022. Os oráculos são usados somente como comparação de regressão, nunca como entrada de cálculo. Antes do fechamento global do subprojeto, o gate deverá ser ampliado para os 30 municípios × 3 censos e para os indicadores domiciliares reconstruídos.

## Regra de desenvolvimento

O código é construído em etapas pequenas e testáveis. Resultados históricos auditados servem apenas como referência independente. O pipeline deve preferir parar com diagnóstico explícito a produzir números aparentemente completos por imputação, inferência de dados protegidos ou tratamento silencioso de ausências.
