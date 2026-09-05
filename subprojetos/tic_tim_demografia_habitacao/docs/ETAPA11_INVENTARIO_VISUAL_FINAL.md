# Etapa 11 — inventário visual final auditado

## Fonte de especificação

Este inventário foi recuperado da matriz editorial canônica `TIC_TIM_MATRIZ_MESTRA_ORGANIZACAO_RELATORIO_DIAGNOSTICO_REGIONAL_v2`, especialmente da aba `12_PLANO_VISUAL_ABNT`.

A aba final deve prevalecer sobre os catálogos preliminares quando houver divergência. Em particular, os números antigos de 987/800 setores para convergência/robustez estão superados. A especificação corrente registra 1.255 setores no critério principal P75 e 959 setores persistentes sob P80.

## Elementos do corpo do relatório

### Capítulo 2 — dinâmica demográfica e transformação dos domicílios

- **T01 — Tabela:** População, crescimento e transformação demográfica dos 30 municípios, 2000–2022.
- **M01 — Mapa:** Crescimento populacional entre 2010 e 2022, escala municipal.
- **M02 — Mapa:** Envelhecimento da população em 2022, escala municipal.
- **M03 — Mapa:** Renovação geracional em 2022, escala municipal; explicitar que CWR é proxy censitária.
- **M04 — Mapa:** Renovação geracional em escala local, nos setores com informação válida; ausências explícitas.
- **G02 — Gráfico:** Mudança da estrutura etária entre 2000 e 2022.
- **G03 — Gráfico:** Crescimento populacional e envelhecimento.
- **G04 — Gráfico:** Crescimento dos domicílios e da população, 2010–2022, com linha de igualdade.
- **G05 — Gráfico:** Redução do tamanho médio dos domicílios, 2000–2022.
- **G06 — Gráfico:** Crescimento dos domicílios unipessoais, 2000–2022.
- **M05 — Mapa:** Participação da população preta e parda na população urbana com informação válida de cor ou raça.
- **G11 — Gráfico:** Participação preta e parda e gravidade físico-urbana, com correlação de Spearman e cautela ecológica.

### Capítulo 3 — famílias analíticas e territorialização

- **M06 — Mapa:** Privação sanitário-ambiental associada à moradia, escala setorial.
- **M08 — Mapa:** Áreas com necessidades habitacionais combinadas, 8.073 setores e 1.255 setores combinados no fechamento histórico P75; categorias não ordinais.
- **T06 — Tabela:** População e domicílios em áreas com necessidades combinadas, por município.

### Capítulo 4 — infraestrutura e habitabilidade

- **M10 — Mapa:** Domicílios com abastecimento de água fora da rede geral, escala municipal.
- **M11 — Mapa:** Domicílios com esgotamento sanitário inadequado, escala municipal.
- **M12 — Prancha cartográfica:** Principais carências da infraestrutura do entorno urbano. A prancha consolida cinco mapas setoriais — bueiro/boca de lobo, calçada, pavimentação, iluminação e arborização — mantendo escalas próprias e valores ausentes explícitos.
- **G09 — Gráfico:** Composição das carências físico-sanitárias.
- **G12 — Gráfico:** Carências físico-sanitárias e carências do entorno, em índices comparativos relativos, não percentuais.

### Capítulo 5 — campos de qualificação local

- **Q01 — Quadro:** Campos de qualificação local e evidências que os sustentam. Não apresentar como programa de obras.

### Capítulo 6 — panorama regional

- **M14 — Mapa:** Panorama regional das dimensões predominantes, escala municipal, categorias não ordinais e empates preservados.
- **G13 — Gráfico:** Crescimento domiciliar e gravidade físico-urbana nos 30 municípios, com Spearman descritivo.
- **T10 — Tabela:** Panorama comparativo dos 30 municípios. Corresponde à Tabela 8 do relatório final; universos e escalas distintos devem permanecer sinalizados.

## Elemento metodológico/anexo

- **M09 — Mapa:** Estabilidade das áreas de necessidades combinadas sob critério mais restritivo. O fechamento histórico correto é 1.255 setores P75, dos quais 959 permanecem identificados no P80, equivalentes a 76,4%. Não utilizar as contagens antigas de 987/800.

## Regras de produção para o pipeline

1. Todos os mapas e gráficos devem ser gerados a partir das bases produzidas pelas etapas anteriores do próprio pipeline.
2. Geometrias devem ser reais e provenientes da malha oficial do IBGE; não são admitidos mapas gerados por IA ou geometrias simuladas.
3. Mapas municipais devem representar o território municipal integral, e não apenas a porção dos 8.073 setores integrados. A malha setorial oficial já baixada na etapa 09 pode ser filtrada pelos 30 códigos municipais e dissolvida para produzir os limites municipais.
4. Mapas setoriais de F1–F4, privação, convergência e robustez devem respeitar os universos analíticos específicos e representar ausências de informação explicitamente.
5. As camadas de raça/cor, FCU e arranjo doméstico produzidas na etapa 10b são descritivas ex post; não podem ser fundidas às famílias analíticas ou à gravidade físico-urbana.
6. As referências numéricas históricas servem como QA. A execução corrente pode registrar deriva de edição, mas não deve ser calibrada para reproduzir artificialmente os valores antigos.
7. Títulos, fontes, notas e unidades devem seguir a terminologia pública estabilizada no Caderno Metodológico e no Relatório Regional.

## Estratégia de implementação

Para reduzir risco e facilitar QA, a etapa 11 deve ser implementada em blocos internos reprodutíveis:

- **11a — tabelas e quadros**;
- **11b — gráficos**;
- **11c — cartografia municipal**;
- **11d — cartografia setorial e prancha do entorno**;
- **11e — manifesto visual e QA de cobertura**.

Esses sufixos são subdivisões operacionais do pipeline e não nomes de gates históricos.