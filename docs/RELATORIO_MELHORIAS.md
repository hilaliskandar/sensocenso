# Versão 0.6.0 — Demografia consolidada

Data: 2025-08-17

Principais mudanças:
- Pirâmides lado a lado (município vs comparador) com alturas alinhadas e mesmas faixas etárias.
- Comparador em percentual (% do total do comparador), mantendo município em valores absolutos.
- Exatamente 11 faixas etárias (décadas), sem redistribuição de dados ou suposições.
- Normalização/ordenação das faixas etárias e padding de categorias vazias para garantir linhas idênticas.
- Layout compacto: redução de margens, legendas e títulos desnecessários; sidebar recolhida nesta página.
- Tabela ABNT: inclui % do total e Δ em pontos percentuais vs comparador.
- Enriquecimento RM/AU via Excel (TIPO_RM_AU, NOME_RM_AU, REGIAO_RM_AU) com cache.

Arquivos afetados (principais):
- pages/10_Demografia.py — layout, normalização de rótulos, comparador %, tabela ABNT.
- src/censo_app/viz.py — ordem eixos/labels, layout compacto, segurança numérica.
- src/censo_app/transform.py — mapeamento RM/AU via Excel, colunas unificadas, grupos etários (11 décadas).
- config/demografia.yaml — ordem das faixas e mapeamentos auxiliares.

Notas:
- O branch main foi atualizado para refletir exatamente esta versão; conflitos anteriores foram resolvidos priorizando a versão atual.
- Branches mantidos: main, deploy/dual-source, indicadores. Demais branches antigos foram removidos.

Próximos passos sugeridos:
- Proteger a branch main nas configurações do repositório (exigir PR, aprovações, checks opcionais).
- Criar release no GitHub apontando para a tag v0.6.0 com este resumo.
