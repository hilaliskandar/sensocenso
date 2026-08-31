# TIC–TIM — Pipeline reprodutível de demografia, habitação e entorno urbano

Este subprojeto reconstrói, de forma reprodutível, o fluxo analítico utilizado no diagnóstico regional TIC–TIM: obtenção das fontes oficiais, harmonização 2000–2010–2022, preparação dos agregados setoriais do Censo 2022, cálculo dos indicadores, territorialização das quatro famílias analíticas, testes de sensibilidade e autocorrelação espacial, sínteses municipais e geração das tabelas e mapas utilizados no relatório.

## Estado

- Relatório regional: redação encerrada e em revisão humana.
- Caderno metodológico público: versão conceitualmente estabilizada.
- Pipeline: etapas 00, 01, 02a e 02b implementadas e validadas em execução viva contra as fontes públicas.
- A etapa 02b reconstruiu 60 linhas (30 municípios × 2000/2010), sem nulos nas três bandas etárias, e passou o gate de regressão com zero divergência nas 20 chaves sentinela.
- A etapa 02c está implementada, mas ainda não é considerada fechada: os Agregados por Setores Censitários de 2022 contêm células `x/X` omitidas pelo IBGE por tratamento de sigilo. O pipeline registra a incidência e interrompe a agregação em vez de transformar valores protegidos em zero ou inferi-los por diferença.

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
```

Para externalizar o armazenamento:

```bash
export TIC_TIM_DATA_ROOT=/dados/tic_tim_demografia
python scripts/run_pipeline.py --etapa implementadas
```

A etapa 01 congela os descritores SIDRA das tabelas 1518 e 3107 e snapshots dos índices públicos do IBGE para agregados setoriais 2022, características urbanísticas do entorno, FCU e CNEFE. Esses snapshots documentam exatamente o catálogo disponível na execução antes que arquivos específicos sejam selecionados e baixados.

## Etapas do pipeline

### 00. Configuração e manifesto de execução

Define os 30 municípios, anos censitários, versões das fontes, diretórios, parâmetros estatísticos, percentis e projeções cartográficas. Valida códigos IBGE, coroas e exclusões antes de qualquer aquisição.

### 01. Aquisição das fontes

Prevê download ou leitura automatizada de Censo 2000/SIDRA, Censo 2010/SIDRA, agregados setoriais 2022, Pesquisa Urbanística do Entorno, malhas, FCU e bases auxiliares necessárias. Cada aquisição registra URL final, data, tamanho e SHA-256. Arquivos em `raw/` não são substituídos silenciosamente.

### 02a. Gate semântico SIDRA

Lê os descritores oficiais e seleciona uma partição etária mutuamente exclusiva de 21 classes: quinquênios de 0–4 até 95–99 e 100 anos ou mais. Isso evita dupla contagem entre faixas agregadas e idades simples presentes simultaneamente nos descritores das tabelas 1518 e 3107. As 21 classes são então agregadas em 0–14, 15–59 e 60+ sem interpolação.

### 02b. Harmonização longitudinal 2000–2010

Baixa os 30 municípios em lotes auditáveis, preserva as respostas JSON brutas e gera `processed/municipal/base_longitudinal_2000_2010.parquet` e `.csv`. O sinal convencional `-` do SIDRA é interpretado como zero segundo as convenções tabulares do IBGE; outros sinais permanecem bloqueadores.

A execução viva fechou 60 linhas, 30 municípios, dois anos, zero nulos nas três bandas e zero divergências no oráculo de regressão de 10 municípios × 2 anos.

### 02c. Incorporação de 2022

A etapa identifica os arquivos `Básico` e `Demografia` no índice oficial congelado, lê as codificações efetivamente publicadas, seleciona setores com `SITUACAO=Urbana` e prepara a agregação das variáveis V01031–V01041 em 0–14, 15–59 e 60+.

O arquivo setorial definitivo aplica tratamento de sigilo. A Nota metodológica n. 06 do Censo 2022 informa que valores omitidos são preenchidos com `x`, inclusive após recodificação global quando ainda restam células de frequência 1 ou 2. Por isso a implementação não transforma `x/X` em zero e não tenta recuperar valores protegidos por diferença. Antes de interromper a etapa, gera `outputs/qa/etapa02c_sigilo_demografia_2022.json`, com incidência por variável, município e setor.

A próxima decisão metodológica deve preservar simultaneamente dois requisitos: manter o universo urbano utilizado no relatório e não violar o tratamento de sigilo do IBGE. A solução será escolhida apenas depois de quantificar a incidência das omissões e confrontar alternativas públicas compatíveis com o mesmo universo.

### 03. Formação e transformação do estoque domiciliar ocupado

Calcula a variação de DPO, a diferença entre crescimento domiciliar e populacional, domicílios unipessoais e demais variáveis utilizadas para caracterizar transformação dos arranjos domiciliares.

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

O fixture versionado usa dez municípios sentinela × dois anos para 2000/2010 e dez sentinelas para o painel urbano de 2022. Os oráculos são usados somente como comparação de regressão, nunca como entrada de cálculo.

## Regra de desenvolvimento

O código é construído em etapas pequenas e testáveis. Resultados históricos auditados servem apenas como referência independente. O pipeline deve preferir parar com diagnóstico explícito a produzir números aparentemente completos por imputação, inferência de dados protegidos ou tratamento silencioso de ausências.
