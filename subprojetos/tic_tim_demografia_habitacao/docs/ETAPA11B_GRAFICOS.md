# Etapa 11b — gráficos públicos reprodutíveis

## Objetivo

A etapa 11b gera automaticamente os gráficos do plano visual final a partir das bases produzidas pelo pipeline, preservando a separação entre edição pública corrente e referências históricas de QA.

A especificação editorial deriva da aba `12_PLANO_VISUAL_ABNT` da matriz canônica `TIC_TIM_MATRIZ_MESTRA_ORGANIZACAO_RELATORIO_DIAGNOSTICO_REGIONAL_v2`. Essa especificação prevalece sobre catálogos preliminares quando houver divergência.

## Gráficos produzidos

- `G02` — Mudança da estrutura etária entre 2000 e 2022.
- `G03` — Crescimento populacional e envelhecimento.
- `G04` — Crescimento dos domicílios e da população, 2010–2022.
- `G05` — Redução do tamanho médio dos domicílios, 2000–2022.
- `G06` — Crescimento dos domicílios unipessoais, 2000–2022.
- `G09` — Composição das carências físico-sanitárias.
- `G11` — Participação preta e parda e carências físico-urbanas nos 30 municípios.
- `G12` — Carências físico-sanitárias e carências do entorno.
- `G13` — Crescimento domiciliar e gravidade físico-urbana nos 30 municípios.

Cada gráfico é salvo em `PNG` e `SVG`. A base tabular efetivamente usada na renderização também é persistida em CSV, de forma que a figura nunca seja o único registro do cálculo.

## Diretórios de saída

- `outputs/graphs/` — PNG e SVG.
- `outputs/data/etapa11b/` — bases tabulares dos gráficos.
- `outputs/qa/etapa11b_graficos.json` — checks estruturais e estatísticos.
- `metadata/manifests/execucao.jsonl` — proveniência das bases, imagens e QA.

## Regras analíticas

### G02

A síntese regional agrega as três faixas etárias harmonizadas — 0–14, 15–59 e 60 anos ou mais — nos anos 2000, 2010 e 2022. As participações devem somar 100% em cada ano.

### G03

Dispersão municipal entre crescimento populacional de 2010 a 2022 e razão de envelhecimento em 2022. O gráfico é descritivo; não expressa causalidade. Apenas casos extremos são rotulados para evitar sobreposição.

### G04

Dispersão municipal entre crescimento dos domicílios particulares ocupados e crescimento populacional, ambos entre 2010 e 2022. A linha de 45 graus é uma referência analítica de igualdade entre os dois crescimentos.

### G05

Compara o tamanho médio dos domicílios em 2000, 2010 e 2022 para os 30 municípios. A unidade é pessoas por domicílio particular ocupado.

### G06

Combina duas escalas explicitamente: número absoluto regional de domicílios unipessoais e participação municipal. Não se deve inferir condição socioeconômica a partir do arranjo domiciliar isoladamente.

### G09

Compara seis carências físico-sanitárias: água fora da rede geral; água sem canalização interna; ausência de banheiro exclusivo ou sanitário; esgotamento inadequado; resíduos inadequados; e precariedade física estrita.

A base municipal da etapa 10 preserva as proporções finais, mas não todos os numeradores e denominadores necessários para recompor de forma rigorosa a proporção regional. Por isso, exclusivamente para G09, a etapa 11b reabre os mesmos agregados oficiais já adquiridos pelo pipeline e reutiliza as fórmulas e seletores de fonte da etapa 10. O resultado regional é persistido em `G09_dados.csv` antes da renderização. Não há nova fonte analítica nem regra paralela.

As ocorrências podem se sobrepor e não representam famílias únicas.

### G11

Dispersão municipal entre participação da população preta e parda na população urbana com informação válida de cor ou raça e gravidade físico-urbana. A correlação de Spearman é calculada na edição corrente; a referência histórica serve apenas para QA. A associação é ecológica e não causal.

### G12

Compara gravidade físico-sanitária e gravidade do entorno. Ambos são índices relativos entre os 30 municípios, variando de 0 a 1, e não percentuais. Sumaré, Várzea Paulista e Nova Odessa são destacados conforme a especificação editorial canônica.

### G13

Dispersão municipal entre crescimento domiciliar de 2010 a 2022 e gravidade físico-urbana. O coeficiente de Spearman é recalculado pela edição corrente. A referência publicada aproximada, `rho=-0,04; p=0,82; n=30`, é QA descritivo, não alvo de calibração.

## Reprodutibilidade e QA

A implementação usa backend não interativo do Matplotlib e fixa parâmetros relevantes para evitar dependência de sessão gráfica. Os arquivos SVG recebem `hashsalt` fixo e metadados variáveis de data são suprimidos. Cada base de gráfico recebe checks de universo, faixas válidas e invariantes pertinentes.

Os testes offline cobrem:

- fechamento de 100% das faixas etárias no G02;
- renderização PNG/SVG;
- universo municipal de 30 municípios;
- cálculos de crescimento do G04;
- redução do tamanho médio e aumento dos unipessoais em dados sintéticos;
- recomposição regional por numerador/denominador para G09;
- cálculo das correlações de Spearman de G11 e G13.

A validação live deve confirmar os gráficos e seus dados com fontes correntes. Referências históricas não podem ser usadas para alterar resultados correntes.
