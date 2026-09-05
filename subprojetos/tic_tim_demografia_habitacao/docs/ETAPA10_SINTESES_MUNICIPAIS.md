# Etapa 10 — sínteses municipais e correlações

## Finalidade

A etapa 10 reconstrói, para os 30 municípios do recorte TIC–TIM, a síntese municipal relativa denominada **gravidade físico-urbana** e as correlações de Spearman empregadas no fechamento do Relatório Regional.

O objetivo é reproduzir o método a partir das fontes públicas correntes e dos produtos gerados pelas etapas anteriores do pipeline. Os resultados históricos publicados são usados como referência independente de QA, e não como valores-alvo para calibração.

A gravidade físico-urbana é uma medida comparativa entre os 30 municípios. Ela não representa déficit habitacional, percentual de domicílios precários, dano observado, escala absoluta de severidade ou prioridade de intervenção. Também é distinta das quatro famílias analíticas utilizadas na territorialização setorial.

## Fontes metodológicas auditadas

A especificação foi recuperada dos seguintes artefatos do acervo TIC–TIM:

- Caderno Metodológico público v1.4 — `TIC_TIM_CADERNO_METODOLOGICO_DEMOGRAFIA_HABITACAO_v1.4_PUBLICO`, Google Drive ID `1irhseplMKlJc6Da1MkyqIifxj3iMTLnb`.
- Relatório Regional v1.8 — `TIC_TIM_DEM_HAB_RELATORIO_REGIONAL_v1.8.docx`, Google Drive ID `1z_ZIF6v82pT_h5tai_h7JTVyimlXsbbM`.
- S05 — `TIC_TIM_GATE17F15C_S05_INDICADORES_PRESSAO_HABITACIONAL_30M_v1.0.xlsx`, Google Drive ID `149q6KjHRKUDeZETJJwbtjTt44N76xatA`.
- S06 — `TIC_TIM_GATE17F15C_S06_MATRIZ_BRUTA_CANONICA_30M_v1.0.xlsx`, Google Drive ID `1I26lMZZUUqrEFwJWCI1KbkH63u3nUwB6`.
- S23 — `TIC_TIM_GATE17F15C_S23_GRAVIDADE_ESCALA_URBANA_30M_v1.1.xlsx`, Google Drive ID `1dN1ZBCa__NAt73cNyS9DGi7hSDIlM1K_`.

Esses artefatos preservam a cadeia de derivação das variáveis elementares, a composição dos três blocos da gravidade físico-urbana e os pares de correlação empregados no relatório.

## Universo e escalas

A etapa trabalha com dois universos que não devem ser confundidos:

1. **Síntese físico-urbana municipal:** utiliza o universo urbano corrente de 9.087 setores, que é a base ampla reconstruída pelas etapas anteriores para a edição pública corrente.
2. **Abrangência da convergência entre famílias:** utiliza exclusivamente o checkpoint territorial histórico de 8.073 setores do Gate18G7F2, preservando o pertencimento ao universo integrado que sustentou a territorialização do relatório.

A coexistência desses universos é deliberada. A edição corrente das bases temáticas pode alterar cobertura e valores sem redefinir retroativamente o universo histórico integrado.

## Indicadores físico-sanitários

Os seis indicadores do bloco físico-sanitário são calculados por composição das categorias censitárias, agregando primeiro os numeradores e denominadores setoriais por município e calculando depois a proporção municipal.

- Água fora da rede: `sum(V00112:V00118) / sum(V00111:V00118)`.
- Água sem canalização: `(V00200 + V00201) / sum(V00199:V00201)`.
- Sem banheiro exclusivo ou sanitário precário: `(V00236 + V00237 + V00238) / sum(V00232:V00238)`.
- Esgotamento inadequado: `sum(V00312:V00316) / sum(V00309:V00316)`.
- Resíduo inadequado: `sum(V00399:V00402) / sum(V00397:V00402)`.
- Precariedade física estrita: `(V00050 + V00052) / sum(V00047:V00052)`.

A **gravidade físico-sanitária** é a média simples dos percentis municipais desses seis indicadores.

## Pressão de ocupação

O bloco de pressão de ocupação é formado por três indicadores:

- Domicílios com 5 ou mais moradores: `sum(V00021:V00026) / sum(V00017:V00026)`.
- Moradores por domicílio particular permanente ocupado: `V00005 / V00004`.
- Pessoas por banheiro exclusivo: `(V00552 + V00553 + V00554 + V00555) / (V00232 + 2*V00233 + 3*V00234 + 4*V00235)`.

No último indicador, a classe `V00235` corresponde a quatro ou mais banheiros e é tratada como quatro. Portanto, o denominador representa uma contagem mínima conservadora de banheiros e o quociente deve ser lido como limite superior conservador de pessoas por banheiro.

A **pressão de ocupação** é a média simples dos percentis municipais desses três indicadores.

## Condição do entorno

São preservados nove atributos do entorno urbano:

- arborização;
- bueiro ou boca de lobo;
- calçada;
- iluminação pública;
- obstáculo na calçada;
- pavimentação;
- ponto de ônibus;
- rampa para cadeirante;
- infraestrutura cicloviária.

Para arborização, bueiro ou boca de lobo, calçada, iluminação, pavimentação, ponto de ônibus, rampa e infraestrutura cicloviária, a ausência (`Não`) representa a condição desfavorável. Para obstáculo na calçada, a presença (`Sim`) representa a condição desfavorável.

Em cada atributo, calcula-se primeiro a prevalência municipal separadamente nos universos de domicílios, moradores e faces, sempre como soma municipal do numerador dividida pela soma municipal do denominador válido. A medida municipal do atributo é a média simples dessas três prevalências. Somente depois dessa média o atributo é convertido em percentil entre os 30 municípios.

A **gravidade do entorno** é a média simples dos percentis dos nove atributos.

## Padronização e gravidade físico-urbana

Cada indicador elementar é convertido em percentil empírico entre os municípios com valor observado. Empates recebem postos médios. No código, a operação equivale a `rank(method="average", pct=True)`.

A síntese final é:

`gravidade_fisico_urbana = mean(gravidade_fisico_sanitaria, pressao_ocupacao, gravidade_entorno)`

Os três blocos possuem peso igual. Nenhuma ponderação por população, domicílios, variância ou julgamento de prioridade é introduzida nessa etapa.

## Convergência entre famílias

A proporção municipal de convergência é calculada sobre o checkpoint integrado de 8.073 setores:

`pct_setores_convergencia_3ou4 = 100 * setores_com_CONVERGENCIA_3_OU_4_igual_1 / setores_integrados_do_municipio`

Setores com classificação temática ausente não são convertidos em convergentes, mas permanecem no denominador territorial integrado. Essa regra reproduz a interpretação da abrangência intramunicipal usada no relatório.

## Correlações de Spearman

A etapa calcula quatro pares:

- crescimento domiciliar 2010–2022 × gravidade físico-urbana;
- crescimento domiciliar 2010–2022 × proporção de setores com convergência entre famílias;
- crescimento domiciliar 2010–2022 × razão de envelhecimento em 2022;
- razão de envelhecimento em 2022 × gravidade físico-urbana.

A correlação de Spearman é calculada com tratamento padrão de empates e exclusão pareada de observações ausentes. Os coeficientes são descritivos dos 30 municípios e não sustentam inferência causal.

O Relatório Regional publicou, com arredondamento, as seguintes referências históricas:

- crescimento domiciliar × gravidade físico-urbana: `rho = -0,04`, `p = 0,82`;
- crescimento domiciliar × convergência setorial: `rho = 0,10`, `p = 0,60`;
- crescimento domiciliar × envelhecimento: `rho = -0,37`, `p = 0,048`;
- envelhecimento × gravidade físico-urbana: `rho = -0,76`, `p < 0,001`.

Esses valores são usados apenas para comparação. Divergências produzidas por revisões das bases públicas são registradas no QA e não são corrigidas artificialmente.

## Saídas

A execução corrente produz:

- `processed/municipal/base_sintese_municipal_2022.csv`;
- `processed/municipal/base_sintese_municipal_2022.parquet`;
- `outputs/qa/etapa10_correlacoes_spearman.csv`;
- `outputs/qa/etapa10_sinteses_municipais.json`.

O JSON de QA registra fórmulas, universos, fontes domiciliares efetivamente selecionadas, valores correntes das correlações e comparação com as referências arredondadas do relatório.

## Modos de execução

No modo `corrente`, a etapa 10 é executável e registra explicitamente a edição observada das fontes públicas.

No modo `historico`, a etapa 10 permanece bloqueada. A regressão histórica rígida só deverá ser implementada quando os payloads exatos das edições de fonte usadas no fechamento original estiverem preservados e identificados de forma suficiente para reprodução integral. Essa separação evita tratar diferenças de edição como erro de cálculo ou ajustar a série corrente para imitar retrospectivamente o produto histórico.
