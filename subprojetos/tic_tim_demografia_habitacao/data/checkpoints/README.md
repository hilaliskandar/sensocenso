# Checkpoint canônico Gate18G7F2

Esta pasta é o ponto de entrada versionado do universo integrado canônico usado nas etapas 07–09 da pipeline TIC–TIM de demografia e habitação.

O checkpoint **não deve ser reconstruído automaticamente a partir das bases públicas correntes**. O fechamento histórico do Gate18G7F2 definiu exatamente **8.073 setores censitários**, com composição de macrotipos **2 = 3.568, 3 = 3.843 e 4 = 662**, pela regra histórica `MACRO_FINAL in {2,3,4} AND ISAU_C3 not null`.

A fonte histórica auditada materializada nesta versão é `TIC_TIM_GATE18G7F2_VALIDACAO_ESPACIAL_ISAU_v5`, aba `19_G7F2_SETORIAL`, preservada no Google Drive da frente de Demografia/Habitação. A conferência independente da materialização confirmou 8.073 códigos de setor únicos com 15 dígitos, nenhum `ISAU_C3` ausente e a composição de macrotipos esperada.

O repositório distribui dois artefatos:

- `TIC_TIM_UNIVERSO_INTEGRADO_CANONICO_G7F2.csv.gz`
- `TIC_TIM_UNIVERSO_INTEGRADO_CANONICO_G7F2.manifest.json`

A compactação gzip é apenas uma representação de armazenamento. A identidade do checkpoint continua sendo a do CSV determinístico com as colunas `codigo_setor` e `macrotipo_checkpoint`. O manifesto registra o SHA-256 dos bytes do CSV descompactado, além do SHA-256 do payload gzip, origem de materialização, regra de seleção, cardinalidade e composição dos macrotipos.

O script `scripts/materializar_checkpoint_g7f2.py` continua sendo a rotina de materialização a partir de uma fonte histórica local auditável. Ele escreve o CSV canônico e o manifesto; a versão distribuída no repositório corresponde ao mesmo CSV compactado byte a byte. O runtime valida o payload e o CSV descompactado antes de liberar a etapa 07 e **não realiza qualquer download**.

Em 2026-09-04 foi confirmado que os runners do GitHub Actions não devem depender de exportações do Google Drive/Sheets. A pipeline usa exclusivamente o checkpoint versionado ou, para auditoria local explícita, uma fonte histórica preparada pelo pesquisador.

Não é permitido substituir o universo de 8.073 setores pela cobertura C3 da edição pública corrente nem ajustar a cardinalidade por inferência.
