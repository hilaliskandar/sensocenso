# Guia ABNT para Gráficos

Este guia resume práticas ABNT para apresentação de gráficos em trabalhos técnicos e acadêmicos.

## Legenda (título) e fonte
- Centralizar o gráfico na página.
- Inserir a legenda acima do gráfico, com:
  - Palavra "Figura" + número de ordem + título, em negrito.
  - Tamanho de fonte recomendado: 11 pt (ou 10–11 pt).
- Inserir a fonte abaixo do gráfico, alinhada à esquerda, fonte 10 pt.
  - Se for de autoria própria com dados públicos, usar: "Fonte: Elaboração própria com dados de <ORIGEM> (<ANO>)."

## Tamanho, layout e borda
- Largura máxima recomendada: 16 cm.
- Manter margens e espaçamentos consistentes.
- Recomenda-se borda preta envolvendo a área do gráfico (linha 1–2 px).
- Em comparativos lado a lado, garantir que o bloco de título tenha a MESMA altura para alinhar o início dos gráficos.

## Conteúdo e clareza
- Gráficos devem ser autoexplicativos: eixos e unidades sempre que pertinente.
- Evitar excesso de elementos visuais; manter paleta limpa.
- Garantir acessibilidade de cores (contraste e distinção para daltônicos quando possível).

## Numeração e lista de figuras
- Numere como “Figura N — Título…”.
- Opcionalmente, forneça uma Lista de Figuras no documento compilado.

## Exemplo de moldura HTML/CSS
- Bloco de legenda com altura fixa (48 px) para alinhar comparativos.
- Fonte abaixo do gráfico.
- Largura máxima 16 cm.

Exemplo (simplificado):

```
<div class="abnt-figure">
  <div class="abnt-caption"><strong>Figura 1 — Título do gráfico</strong></div>
  [gráfico]
  <div class="abnt-source">Fonte: Elaboração própria com dados do IBGE (2022).</div>
</div>
```

CSS sugerido:

```
.abnt-figure { max-width: 16cm; margin: 0.25rem auto; }
.abnt-caption { text-align:center; font-weight:700; font-size:11pt; line-height:1.2; height:48px; display:flex; align-items:center; justify-content:center; }
.abnt-source { font-size:10pt; text-align:left; margin-top:6px; }
```
