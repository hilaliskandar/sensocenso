# Etapa 11e — manifesto visual e QA de cobertura

A etapa 11e encerra a produção visual reprodutível da etapa 11. Ela não recalcula indicadores: confronta as saídas das etapas 11a–11d com o inventário visual final registrado em `docs/ETAPA11_INVENTARIO_VISUAL_FINAL.md` e na aba `12_PLANO_VISUAL_ABNT` da matriz editorial canônica.

O inventário final contém 25 elementos editoriais. Vinte e quatro são saídas diretamente auditáveis do pipeline. O Q01, `Campos de qualificação local e evidências que os sustentam`, já está produzido no Relatório Regional v1.8 e é contabilizado como elemento editorial externo ao pipeline.

Para cada saída do pipeline, a etapa verifica existência e tamanho do arquivo. PNGs são abertos e validados por decodificação e dimensão mínima; SVGs são analisados como XML; CSVs devem conter cabeçalho e dados. Cada arquivo auditado recebe SHA-256. O XLSX consolidado da etapa 11a deve conter exatamente as abas T01, T06 e T10.

A etapa reabre os QAs 11a–11d e verifica os invariantes principais: três tabelas públicas; nove gráficos; 30 territórios municipais integrais; M04 com 7.474 valores válidos; M06 com 8.067; M08 com 1.304 convergentes correntes; M09 com 1.016 persistentes e 945 com o mesmo vetor; M12 com universo de 9.087 setores.

As referências históricas permanecem 1.255 setores P75 para M08, 959 persistentes P75–P80 e 886 persistentes com o mesmo vetor para M09. Elas servem apenas como QA. A edição corrente não é ajustada para reproduzi-las. As contagens antigas 987/800 permanecem obsoletas.

Saídas da 11e:

- `outputs/qa/etapa11e_manifesto_visual.csv`;
- `outputs/qa/etapa11e_integridade_arquivos.csv`;
- `outputs/qa/etapa11e_manifesto_visual.json`.

O QA automatizado verifica cobertura e integridade estrutural. A inspeção visual editorial dos PNGs permanece uma verificação separada antes da revisão humana do relatório.
