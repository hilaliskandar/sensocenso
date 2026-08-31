# TIC–TIM — Pipeline reprodutível de demografia, habitação e entorno urbano

Este subprojeto reconstrói, de forma reprodutível, o fluxo analítico utilizado no diagnóstico regional TIC–TIM: obtenção das fontes oficiais, harmonização 2000–2010–2022, preparação dos agregados setoriais do Censo 2022, cálculo dos indicadores, territorialização das quatro famílias analíticas, testes de sensibilidade e autocorrelação espacial, sínteses municipais e geração das tabelas e mapas utilizados no relatório.

## Estado

- Relatório regional: redação encerrada e em revisão humana.
- Caderno metodológico público: versão conceitualmente estabilizada.
- Pipeline: etapas 00 e 01 já possuem implementação funcional de configuração, proveniência e descoberta/congelamento inicial das fontes.

## Princípios de reprodução

1. Usar somente fontes públicas e versões explicitamente registradas.
2. Preservar numeradores, denominadores, categorias originais e flags de cobertura antes de derivar indicadores.
3. Não converter ausência, supressão ou não aplicabilidade em zero.
4. Manter separadas as escalas municipal, setorial, moradores, domicílios e faces de logradouro.
5. Tratar variáveis municipais propagadas aos setores apenas como contexto compartilhado, nunca como observação microlocal.
6. Registrar parâmetros e universos efetivos de cada etapa.
7. Produzir artefatos intermediários auditáveis e hashes quando aplicável.
8. Reproduzir os elementos visuais a partir das bases analíticas, e não a partir de imagens finais.
9. Não depender de Google Drive, nomes de usuário ou caminhos particulares de máquina.

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
│   └── fontes/
├── scripts/
│   └── run_pipeline.py
├── tests/
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

Prevê download ou leitura automatizada de:

- Censo Demográfico 2000 — SIDRA, inclusive Tabela 1518;
- Censo Demográfico 2010 — Sinopse e tabelas SIDRA utilizadas na harmonização;
- Censo Demográfico 2022 — agregados por setores censitários;
- Pesquisa Urbanística do Entorno 2022;
- malha de setores censitários e malha municipal;
- Favelas e Comunidades Urbanas 2022;
- bases auxiliares do IBGE, quando necessárias à reprodução.

Cada aquisição deve registrar URL final, data, tamanho e SHA-256. Arquivos em `raw/` não são substituídos silenciosamente.

### 02. Harmonização longitudinal

Reconstrói a série municipal 2000–2010–2022, com prioridade para as faixas 0–14, 15–59 e 60+; calcula população, participação etária, razão de envelhecimento, crescimento populacional, crescimento dos domicílios particulares ocupados e tamanho médio aproximado dos domicílios.

### 03. Formação e transformação do estoque domiciliar ocupado

Calcula a variação de DPO, a diferença entre crescimento domiciliar e populacional, domicílios unipessoais e demais variáveis utilizadas para caracterizar transformação dos arranjos domiciliares.

### 04. Renovação demográfica recente

Calcula a razão criança–mulher (0–4 / mulheres 15–49 × 1.000), preservando a interpretação como proxy censitária de renovação demográfica recente, e não como taxa de fecundidade ou natalidade.

### 05. Privação sanitário-ambiental censitariamente observável

Reconstrói os domínios de água, esgotamento, resíduos e a proxy censitária de drenagem baseada na presença/ausência de bueiro ou boca de lobo; calcula o ISAU e a privação `1 - ISAU`, com os mesmos critérios de cobertura do fechamento analítico.

### 06. Ausência de atributos selecionados do entorno urbano

Calcula os cinco componentes utilizados na família F3: drenagem/bueiro, calçada, pavimentação, iluminação e arborização. A regra final identifica a família quando pelo menos dois dos cinco sinais estão relativamente elevados segundo o corte adotado.

### 07. Quatro famílias analíticas

Reconstrói:

- **F1** — dinâmica do estoque domiciliar ocupado e renovação demográfica recente;
- **F2** — privação sanitário-ambiental censitariamente observável;
- **F3** — ausência de atributos selecionados do entorno urbano;
- **F4** — estrutura etária e arranjos domiciliares.

A convergência multidimensional corresponde à presença de três ou quatro famílias, sem interpretação automática como déficit, severidade ou prioridade.

### 08. Cortes relativos e sensibilidade

Calcula P75 como referência principal e P80 como teste de estabilidade. Variáveis cujo percentil seja zero seguem a regra específica documentada no caderno metodológico, evitando que valor zero seja classificado como carência elevada.

### 09. Validação espacial

Constrói vizinhança Queen sobre a malha censitária, identifica ilhas, reproduz o Moran global com o número de permutações definido na configuração e registra o universo efetivamente utilizado.

### 10. Comparações municipais

Produz sínteses municipais, correlações de Spearman e os indicadores comparativos usados no panorama regional, mantendo separadas medidas municipais relativas das quatro famílias da territorialização.

### 11. Produtos tabulares e cartográficos

Gera automaticamente tabelas de síntese, matrizes municipais, arquivos geoespaciais e mapas em padrão editorial definido, incluindo os mapas regionais, mapas setoriais e pranchas multipainel do entorno.

### 12. QA e reprodutibilidade

Executa testes de unicidade de chaves, universos, denominadores, faixas válidas, cobertura espacial, equivalência de agregações, estabilidade P75/P80 e regressão contra valores auditados.

## Regra de desenvolvimento

O código é construído em etapas pequenas e testáveis. Os valores de referência usados nos testes são extraídos dos produtos auditados do projeto, mas nunca são usados como substitutos das fontes originais. Dados brutos não são versionados quando a fonte pública permite reobtenção automatizada.

A meta operacional seguinte é selecionar, a partir dos snapshots congelados e dos descritores SIDRA, as consultas e arquivos necessários para produzir a primeira base longitudinal municipal 2000–2010–2022 em `processed/municipal/`, com QA automático contra os resultados auditados.
