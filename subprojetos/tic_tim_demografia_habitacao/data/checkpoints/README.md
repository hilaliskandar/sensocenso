# Checkpoint canônico Gate18G7F2

Esta pasta é o ponto de entrada versionado do universo integrado canônico usado nas etapas 07–09 da pipeline TIC–TIM de demografia e habitação.

O checkpoint **não deve ser reconstruído automaticamente a partir das bases públicas correntes**. O fechamento histórico do Gate18G7F2 definiu exatamente **8.073 setores censitários**, com composição de macrotipos **2 = 3.568, 3 = 3.843 e 4 = 662**, pela regra histórica `MACRO_FINAL in {2,3,4} AND ISAU_C3 not null`.

Arquivos esperados quando a fonte histórica auditada estiver disponível:

- `TIC_TIM_UNIVERSO_INTEGRADO_CANONICO_G7F2.csv`
- `TIC_TIM_UNIVERSO_INTEGRADO_CANONICO_G7F2.manifest.json`

O CSV deve conter apenas `codigo_setor` e `macrotipo_checkpoint`. O manifesto registra origem de materialização, regra de seleção, SHA-256 do CSV, cardinalidade e composição dos macrotipos. O carregador valida todos esses elementos antes de liberar a etapa 07.

A materialização é feita uma única vez por `scripts/materializar_checkpoint_g7f2.py`, a partir de um arquivo histórico local auditável que contenha código do setor, macrotipo final e ISAU-C3. O runtime não deve depender de exportações do Google Drive/Sheets: em 2026-09-04 os runners do GitHub Actions receberam HTTP 401 tanto para G7E/G7F2 quanto para espelhos posteriores testados.

Enquanto o CSV e o manifesto canônicos não estiverem presentes, as etapas 07–09 devem falhar de forma explícita. Não é permitido substituir o universo de 8.073 setores pela cobertura C3 da edição pública corrente nem ajustar a cardinalidade por inferência.
