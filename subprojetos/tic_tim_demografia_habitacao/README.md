# TIC–TIM — Pipeline reprodutível de demografia, habitação e entorno urbano

Este subprojeto reconstrói, de forma reprodutível, o fluxo analítico utilizado no diagnóstico regional TIC–TIM: obtenção das fontes oficiais, harmonização 2000–2010–2022, preparação dos agregados setoriais do Censo 2022, cálculo dos indicadores, territorialização das quatro famílias analíticas, testes de sensibilidade e autocorrelação espacial, sínteses municipais e geração das tabelas e mapas utilizados no relatório.

## Estado

- Relatório regional: redação encerrada e em revisão humana.
- Caderno metodológico público: versão conceitualmente estabilizada.
- Pipeline: início da reconstrução em código a partir dos produtos auditados e da documentação metodológica.

## Princípios de reprodução

1. Usar somente fontes públicas e versões explicitamente registradas.
2. Preservar numeradores, denominadores, categorias originais e flags de cobertura antes de derivar indicadores.
3. Não converter ausência, supressão ou não aplicabilidade em zero.
4. Manter separadas as escalas municipal, setorial, moradores, domicílios e faces de logradouro.
5. Tratar variáveis municipais propagadas aos setores apenas como contexto compartilhado, nunca como observação microlocal.
6. Registrar parâmetros e universos efetivos de cada etapa.
7. Produzir artefatos intermediários auditáveis e hashes quando aplicável.
8. Reproduzir os elementos visuais a partir das bases analíticas, e não a partir de imagens finais.

## Estrutura proposta

```text
subprojetos/tic_tim_demografia_habitacao/
├── README.md
├── pyproject.toml
├── config/
│   ├── municipios.yml
│   ├── fontes.yml
│   └── parametros.yml
├── src/tic_tim_demografia/
│   ├── __init__.py
│   ├── cli.py
│   ├── fontes/
│   ├── harmonizacao/
│   ├── indicadores/
│   ├── territorializacao/
│   ├── espacial/
│   ├── produtos/
│   └── qa/
├── scripts/
│   └── run_pipeline.py
├── tests/
└── docs/
```

## Etapas do pipeline

### 00. Configuração e manifesto de execução

Define os 30 municípios, anos censitários, versões das fontes, diretórios, parâmetros estatísticos, percentis e projeções cartográficas.

### 01. Aquisição das fontes

Prevê download ou leitura automatizada de:

- Censo Demográfico 2000 — SIDRA, inclusive Tabela 1518;
- Censo Demográfico 2010 — Sinopse e tabelas SIDRA utilizadas na harmonização;
- Censo Demográfico 2022 — agregados por setores censitários;
- Pesquisa Urbanística do Entorno 2022;
- malha de setores censitários e malha municipal;
- Favelas e Comunidades Urbanas 2022;
- bases auxiliares do IBGE, quando necessárias à reprodução.

Cada aquisição deve registrar URL, data de obtenção, tamanho, versão/edição identificável e hash do arquivo bruto.

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

Executa testes de:

- unicidade de chaves;
- coerência de universos e denominadores;
- percentuais em faixas válidas;
- cobertura espacial;
- equivalência de agregações;
- estabilidade P75/P80;
- consistência dos produtos finais com valores de referência auditados.

## Regra de desenvolvimento

O código será construído em etapas pequenas e testáveis. Os valores de referência usados nos testes serão extraídos dos produtos auditados do projeto, mas os dados brutos não serão versionados no GitHub quando forem grandes ou quando a fonte pública permitir reobtenção automatizada.

A primeira meta operacional é reproduzir, do zero, a base longitudinal municipal e o universo setorial 2022. Em seguida serão reconstruídos ISAU/F2, F3, F1/F4, convergência multidimensional, validação espacial e, por fim, mapas e tabelas.
