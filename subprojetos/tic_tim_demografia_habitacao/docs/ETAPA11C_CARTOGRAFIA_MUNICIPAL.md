# Etapa 11c — cartografia municipal reprodutível

## Finalidade

A etapa 11c gera a cartografia municipal prevista no inventário visual final do diagnóstico TIC–TIM a partir das bases produzidas pelo próprio pipeline e de geometrias reais da malha oficial de setores censitários 2022 do IBGE.

A especificação editorial de referência é a aba `12_PLANO_VISUAL_ABNT` da matriz `TIC_TIM_MATRIZ_MESTRA_ORGANIZACAO_RELATORIO_DIAGNOSTICO_REGIONAL_v2`. As regras de apresentação seguem a aba `11_PADRAO_ABNT_VISUAIS`.

## Mapas produzidos

- `M01` — Crescimento populacional entre 2010 e 2022, em %.
- `M02` — Envelhecimento da população em 2022, razão de pessoas com 60 anos ou mais por 100 crianças de 0–14 anos.
- `M03` — Renovação geracional em 2022, proxy censitária de crianças de 0–4 anos por mil mulheres de 15–49 anos.
- `M05` — Participação da população preta e parda na população urbana com informação válida de cor ou raça, em %.
- `M10` — Domicílios com abastecimento de água fora da rede geral, em % do universo urbano de referência.
- `M11` — Domicílios com esgotamento sanitário inadequado, em % do universo urbano de referência.
- `M14` — Panorama regional das dimensões predominantes, em categorias não ordinais.

## Geometria e referência cartográfica

Os mapas municipais representam o território municipal integral. O limite de cada município é derivado pela dissolução dos setores censitários 2022 da malha oficial do IBGE, agrupados pelo prefixo municipal de sete dígitos. O universo territorial de 8.073 setores integrados não é usado para recortar os limites municipais.

A geometria de origem é preservada no CRS publicado pelo IBGE e a renderização é feita em `EPSG:31983` — SIRGAS 2000 / UTM zona 23S — para manter medidas cartográficas em metros na área de estudo.

## Classificação dos mapas contínuos

M01, M02, M03, M05, M10 e M11 usam cinco classes por quantis municipais, calculadas apenas entre valores válidos da edição corrente. Os limites das classes são derivados a cada execução e gravados no QA. A classificação é editorial e não constitui limiar analítico ou norma de prioridade.

No M01, municípios com crescimento negativo recebem hachura adicional para que o sinal de redução não dependa apenas da classe cromática. Valores ausentes, quando existirem, permanecem explicitamente representados.

## Regra do M14

O M14 sintetiza as quatro famílias analíticas públicas com a nomenclatura canônica do Caderno Metodológico público v1.4:

- F1 — Dinâmica do estoque domiciliar ocupado e renovação demográfica recente;
- F2 — Privação sanitário-ambiental censitariamente observável;
- F3 — Ausência de atributos selecionados do entorno urbano;
- F4 — Estrutura etária e arranjos domiciliares.

A nomenclatura descreve diretamente o que os indicadores observam. Em particular, F4 não é tratada como “adaptação demográfica”, pois envelhecimento e arranjos domiciliares caracterizam estrutura e mudança populacional e não uma resposta adaptativa já realizada.

Para cada município, calcula-se a participação de setores sinalizados entre os setores observados de cada família dentro do universo integrado. A família predominante é a de maior participação municipal. Empates numéricos são preservados como combinações, por exemplo `F1+F4`; não há desempate arbitrário. As categorias são descritivas e não representam hierarquia, gravidade ou prioridade normativa.

## Saídas

A etapa grava:

- `outputs/maps/M01.png` e `.svg`;
- `outputs/maps/M02.png` e `.svg`;
- `outputs/maps/M03.png` e `.svg`;
- `outputs/maps/M05.png` e `.svg`;
- `outputs/maps/M10.png` e `.svg`;
- `outputs/maps/M11.png` e `.svg`;
- `outputs/maps/M14.png` e `.svg`;
- `outputs/data/11c/base_cartografia_municipal_30.csv`;
- `processed/espacial/base_cartografia_municipal_30.gpkg`;
- `processed/espacial/base_cartografia_municipal_30.parquet`;
- `outputs/qa/etapa11c_cartografia_municipal.json`.

O QA registra a fonte da geometria, CRS de origem e de renderização, método de dissolução, limites das classes de cada mapa contínuo, contagem de valores válidos/ausentes, categorias do M14, empates, nomenclatura pública das famílias e lista completa de saídas.

## Regras de aceite

1. Exatamente 30 territórios municipais únicos e não vazios.
2. Limites derivados da malha oficial do IBGE, sem geometrias simuladas.
3. Território municipal integral nos sete mapas.
4. Indicadores municipais derivados exclusivamente das bases validadas do pipeline.
5. Classes contínuas e seus limites registrados no QA.
6. Empates no M14 preservados explicitamente.
7. Nomenclatura de F1–F4 idêntica à especificação pública do Caderno Metodológico v1.4.
8. Título acima, fonte e nota abaixo, unidade/legenda autossuficientes, escala gráfica e orientação cartográfica.
9. Saídas PNG e SVG determinísticas, acompanhadas da base tabular e da base espacial reproduzível.
