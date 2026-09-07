# Valinhos - Volume I APOND - status em 2026-09-07

Status: `GATE_VOLUME_I_QA_OK`.

## Insumos canônicos

- Município: Valinhos, código IBGE 3556206.
- Referência territorial corrente: 233 setores, sete APONDs, distribuição 30/24/29/27/56/32/35.
- Base estatística: `TIC_TIM_Censo2022_Valinhos_Tabelas_Normalizadas_APOND_168_Entorno_v2.xlsx`.
- Cartografia: `TIC_TIM_Censo2022_Valinhos_APOND_base_territorial_v1.gpkg`, EPSG:4674, 9.753 faces.

## Procedimento de produção

O Volume I foi gerado a partir do builder derivado do procedimento validado em Vinhedo, adaptado para sete APONDs e para as referências amostrais/populacionais de Valinhos. Por limitação operacional de tempo de renderização, a produção foi executada em lotes de ordens 1-10, 11-20, 21-30, 31-40, 41-50, 51-60, 61-70 e 71-76. As figuras previamente produzidas foram reutilizadas por cache quando disponíveis; os dados não foram recalculados entre lotes.

Na consolidação, foram removidos o front matter e a página de controle repetidos nos lotes intermediários. A numeração de figuras foi parametrizada globalmente, resultando em `Figura I.2` a `Figura I.77`. A paginação foi recalculada segundo a extensão real de cada lote, inclusive páginas adicionais de continuação de tabelas, resultando em páginas 1-158 sem lacunas ou duplicações.

## QA final

- PDF final: 158 páginas.
- Tabelas: 76, numeração 1-76 completa.
- Figuras analíticas: 76, numeração I.2-I.77 completa.
- Menções residuais a Vinhedo: 0.
- Preflight: PDF aberto com sucesso; não criptografado; não classificado como escaneado.
- Render integral: 158 páginas renderizadas; 0 PNGs corrompidos.
- Inspeção visual amostral da abertura, diretório, tabelas e mapas ao longo de todo o volume: sem sobreposição ou clipping detectado.
- SHA-256 do PDF: `4da5a5436a31250f2adedfb11253ca0536348af90bfc54503e11531c1a517c9a`.

## Persistência no Google Drive

- PDF final: Drive ID `1JWm0BcDNsadBg0PKhByR-7-A8ZdUWXrk`.
- QA Volume I: Drive ID `1XZ4smZCRPN6Mh4L91QIJrbtsWOnyEZAb`.
- Builder utilizado: Drive ID `1Nw-XlOWks8_EUrUF8O-Z2hYGLQkeKto6`.

## Próximo passo

Prosseguir para o Volume II usando a mesma base v2 e a mesma cartografia já auditadas. Não reabrir os gates de normalização, Entorno, base v2 ou cartografia salvo surgimento de inconsistência nova e documentada.
