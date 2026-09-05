# Transição de fase — relatório encerrado, pipeline iniciado

Data de referência: 2026-08-30.

## Fase encerrada

A redação técnica do Relatório Regional de diagnóstico demográfico, habitacional e urbano foi encerrada e encaminhada para revisão humana. O Caderno Metodológico público foi estabilizado conceitualmente e acompanha o relatório como documento de método.

A fase encerrada não significa congelamento definitivo do conteúdo editorial: correções decorrentes da revisão humana poderão gerar nova versão do relatório, mas não reabrem automaticamente a modelagem analítica já auditada.

## Nova frente ativa

A frente ativa passa a ser a reconstrução computacional integral e reprodutível da análise no repositório `hilaliskandar/sensocenso`, subprojeto:

`subprojetos/tic_tim_demografia_habitacao/`

Branch de desenvolvimento:

`tic-tim-demografia-pipeline`

Issue de controle:

`#12 — TIC–TIM: reconstruir pipeline reprodutível de demografia e habitação`

PR de desenvolvimento:

`#13 — Inicia pipeline reprodutível TIC–TIM de demografia e habitação` (draft)

## Regra de continuidade

O pipeline deve reconstruir os resultados a partir das fontes públicas, e não copiar bases finais auditadas. Os produtos auditados funcionam apenas como oráculos de QA e regressão.

Cada etapa deve registrar fonte, versão, URL, data de obtenção, hash dos arquivos brutos, universo efetivo, parâmetros, saída e testes de consistência. Dados ausentes ou suprimidos nunca devem ser convertidos silenciosamente em zero.

## Primeiro marco funcional

O primeiro marco é reproduzir a base longitudinal municipal 2000–2010–2022 para os 30 municípios, começando pela aquisição SIDRA/IBGE e pela harmonização das faixas 0–14, 15–59 e 60+. Só depois desse gate o desenvolvimento avança para indicadores domiciliares, CWR, ISAU, entorno, famílias analíticas, sensibilidade, análise espacial e produtos cartográficos.
