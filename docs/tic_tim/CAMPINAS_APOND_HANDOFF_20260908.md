# Campinas — Caderno APOND — handoff técnico

Data de fechamento: 2026-09-08
Branch: `tic-tim-campinas-apond-pipeline`
Estado: `GATE_CAMPINAS_CADERNO_COMPLETO_QA_OK — CONSOLIDADO_DRIVE_PENDENTE_TRANSPORTE`

## Referência territorial

- Município: Campinas (`3509502`).
- 35 APONDs correntes, códigos `3509502002`–`3509502036`.
- 2.592 setores correntes na Matriz Mestra; controle histórico somava 2.523.
- A composição corrente prevalece para Entorno e cartografia.
- Referência territorial Drive: `1LGCZRp90sXD36GHux6HCCw4UKM7qUNnH`.

## Estatística

- Base 168 normalizada: PASS; 157 variáveis completas, 11 de cobertura parcial, 0 sem base, 0 falhas.
- Auditoria independente: 5.993 checks, 0 erros.
- Base 168+Entorno v2: Drive `1hCOm2HxydBNjGmsQS0jFaz4ZsfETwoxS`.
- Entorno oficial V050/V052/V054: 105 variáveis, 30 distribuições, 1.080 grupos de QA, PASS.

## Cartografia

- 2.592 setores, 35 APONDs, 49.372 faces, EPSG:4674.
- GeoPackage Drive: `1yZ1GRiNt7jPwnl5O_F18wUurRQaYgF7E`.
- Mapa de abertura: `1xIX56TBp6vMogzocloQ1INXSe0owjfMG`.
- Reconciliação geométrica independente: diferença simétrica 0 m².

## Adaptação editorial para 35 APONDs

As matrizes foram organizadas em quatro blocos territoriais, sem alteração de chaves ou conteúdo estatístico:

1. A01–A09
2. A10–A18
3. A19–A27
4. A28–A35

A coluna MUNICIPIO é mantida como referência. O Volume II preserva os três modos editoriais canônicos: matriz, tabela hierarquizada e síntese de alta cardinalidade. A distribuição integral permanece na base auditada.

## Produtos finais

- Volume I — 246 páginas — Drive `1qxb80l0UHNhHGkSWb9caAoFx3ovrbtjF`.
- Volume II — 350 páginas — Drive `1PAfmpIH-0ACaULgswlgAK3at98R_Aqo-`.
- Volume III — 265 páginas — Drive `1Jtz_F30RWFnOnFr-ypicd9N1uvYsx3vp`.
- QA consolidado — Drive `12PPF6T_9TNCQxDJr9oDpKZgr7zzaD2kt`.
- Manifesto de integridade — Drive `1kyuynTu4P_VYg3RIoV7Yx7lUFF9jn9gw`.

O Volume III originalmente continha 28 páginas de abertura repetidas provenientes das execuções parciais. Essas páginas foram removidas antes da promoção. Os três volumes receberam repaginação global de rodapé e passaram por preflight e QA visual dirigido.

## Consolidado auditado

- Nome: `TIC_TIM_Censo2022_Campinas_Caderno_APOND_CONSOLIDADO_v1.pdf`.
- 861 páginas = 246 + 350 + 265.
- Tamanho: 155.788.412 bytes.
- SHA-256: `d6dc87b5ad57287161a9e73a39672b34f5f04a956b480bed3b779c3ae29c3686`.
- Preflight: PASS.
- QA visual: PASS.

O consolidado ainda não está no Drive porque o conector utilizado nesta sessão impõe limite de 100 MB por upload. Essa pendência é exclusivamente de transporte/armazenamento. Não reabrir gates estatísticos, de Entorno, cartográficos ou editoriais. Até a transferência do consolidado, os três volumes no Drive são os artefatos canônicos de entrega.

## Continuidade

Campinas encerra o lote de nove municípios. A etapa seguinte é revisão transversal/final de consistência, inventário e empacotamento dos entregáveis. Quando houver uma rota de upload superior a 100 MB, transferir o consolidado, validar páginas e SHA-256/equivalência documental e remover a ressalva `CONSOLIDADO_DRIVE_PENDENTE_TRANSPORTE` do handoff e dos controles.