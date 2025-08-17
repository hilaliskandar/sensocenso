# Guia ABNT para Tabelas

Este guia resume práticas ABNT para apresentação de tabelas.

## Título e fonte
- Título acima da tabela, centralizado, em negrito, no formato:
  - "Tabela N — Descrição da tabela"
  - Tamanho recomendado: 11 pt (ou 10–11 pt)
- Fonte abaixo, alinhada à esquerda, 10 pt.
  - Ex.: "Fonte: Censo 2022 — IBGE."

## Estrutura e estilo
- Tabelas abertas lateralmente (sem bordas verticais), com linhas superior e inferior mais espessas.
- Alinhar números à direita e textos à esquerda.
- Usar separadores de milhares e adequada precisão decimal.
- Garantir legibilidade: altura de linhas e espaçamento regular.

## Notas e escopo
- Notas explicativas após a fonte (se necessário), indicando filtros aplicados, exclusões e hipóteses.
- Quando houver comparação, explicitar como os percentuais e deltas foram calculados.

## Exemplo de moldura HTML/CSS

```
<div class="abnt-table-title"><strong>Tabela 1 — Distribuição por faixa etária…</strong></div>
<table class="abnt">
  ...
</table>
<div class="abnt-source">Fonte: Censo 2022 — IBGE.</div>
```

CSS sugerido:

```
.abnt-table-title { text-align:center; font-weight:700; font-size:11pt; }
.abnt { border-collapse: collapse; width: 100%; border-top: 2px solid #000; border-bottom: 2px solid #000; font-family: Arial, 'Times New Roman', serif; font-size: 12px; }
.abnt th, .abnt td { padding: 6px 10px; text-align: right; border-left: none; border-right: none; }
.abnt th:first-child, .abnt td:first-child { text-align: left; }
```
