# TIC-TIM Caieiras APOND — checklist de promoção

Estado corrente: `GATE_ENTORNO_QA_INTERNO_OK`.

## Concluído

- [x] Branch de trabalho separada da `main`.
- [x] Configuração municipal Caieiras A01–A07.
- [x] Composição territorial auditada: 207 setores / 7 APONDs.
- [x] Normalização das 168 variáveis com QA interno.
- [x] Regras semânticas E01–E10 versionadas.
- [x] Fonte oficial específica do Entorno identificada no IBGE.
- [x] Agregação V050/V052/V054 executada a partir dos três CSVs oficiais.
- [x] Ausência de registro publicado preservada como ausência, não zero.
- [x] 105 contadores de Entorno agregados por APOND.
- [x] 30 distribuições calculadas para 7 APONDs + município.
- [x] 240 grupos de QA aprovados.
- [x] Nenhum valor não numérico publicado para os setores de Caieiras.
- [x] Artefatos de QA gerados no GitHub Actions run 34000432850.

## Pendente antes da promoção editorial

- [ ] Incorporar Entorno à base normalizada e gerar `v2`.
- [ ] Verificar reconciliação estrutural da base v2 contra a v1 + Entorno.
- [ ] Parametrizar builders dos Volumes I–III para Caieiras.
- [ ] Substituir A01–A27 / blocos 14+13 por bloco único A01–A07.
- [ ] Conectar cartografia real das sete APONDs e faces de logradouro.
- [ ] Gerar PDF piloto curto.
- [ ] Executar QA visual do piloto: cortes, sobreposições, tipografia, mapas, legendas e notas.
- [ ] Reconciliar números exibidos no piloto com a base v2.
- [ ] Somente após aprovação do piloto, gerar Volumes I–III e consolidado.
- [ ] Renderizar todas as páginas e executar preflight final.
- [ ] Manter PR #16 em rascunho até esses itens serem concluídos.

## Evidência do gate Entorno

Run: `34000432850`  
Artifact ID: `9979325831`  
Artifact SHA-256: `e8eb883ce9538013650023ee4b3fc5fbf44169d08c77d944ffe7e10668841e21`  
QA distribuições: `PASS`  
Erros: `[]`  
Máximo desvio de fechamento: `1.4210854715202004e-14`.
