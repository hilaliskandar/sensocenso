# Etapa 12 — QA final de reprodutibilidade

A etapa 12 encerra o pipeline reprodutível corrente de demografia e habitação do TIC–TIM. Ela não recalcula indicadores: consolida os registros produzidos pelas etapas 00–11e e verifica se a execução completa preservou a sequência canônica, os universos, o checkpoint territorial, os invariantes analíticos e a cobertura editorial já auditados.

O fechamento distingue três situações. A reprodutibilidade da edição corrente deve ser integral; diferenças entre a edição corrente das fontes públicas e o fechamento histórico são registradas como deriva de edição e não são corrigidas artificialmente; e uma limitação histórica específica permanece explícita para o Moran global, cuja transformação/normalização canônica dos pesos do artefato de fechamento ainda não foi recuperada para reprodução numérica bit a bit.

A etapa verifica, entre outros pontos:

- a presença das etapas 00–11e na ordem canônica e seus estados esperados;
- 30 municípios e os anos censitários 2000, 2010 e 2022;
- 90 linhas nas bases longitudinal e domiciliar e 9.087 setores urbanos correntes;
- o checkpoint de 8.073 setores com SHA-256 lógico `72d6490f46c4cef588e2fed7935c69d4d1673c563546f96dfb7683475b13fd6f`;
- 177 ilhas Queen, 19.314 arestas Queen únicas e 304 arestas intermunicipais;
- 1.304 setores convergentes no P75, 1.016 persistentes P75–P80 e 945 persistentes com o mesmo vetor na edição corrente;
- as referências históricas 1.255, 959 e 886 apenas como QA, sem retorno das contagens obsoletas 987/800;
- 557 setores em FCU e 236 FCU distintas no universo dos 30 municípios;
- os invariantes cartográficos da etapa 11d e a cobertura dos 25 elementos editoriais auditada na etapa 11e.

Saídas:

- `outputs/qa/etapa12_qa_final.json`;
- `outputs/qa/etapa12_resumo_final.md`.

Execução isolada:

```bash
python scripts/run_pipeline.py --etapa 12
```

No modo `historico`, a etapa 12 permanece deliberadamente bloqueada enquanto não for recuperada a transformação/normalização canônica dos pesos usada no Moran histórico. Isso não impede o fechamento da reprodutibilidade da edição corrente.
