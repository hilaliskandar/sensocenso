# Execução do Entorno — Caieiras

## Fonte canônica

Utilizar exclusivamente os três agregados oficiais específicos de Características urbanísticas do entorno dos domicílios do Censo 2022:

- V05000–V05034 — domicílios;
- V05200–V05234 — moradores;
- V05400–V05434 — faces.

A rota antiga baseada em `SP_setores_CD2022.dbf` não é canônica para Entorno porque a malha com atributos não contém essas séries.

## Execução reproduzível

O workflow `.github/workflows/tic_tim_caieiras_entorno_qa.yml`:

1. valida `data/tic_tim/caieiras_setor_apond_207.csv`;
2. baixa os três ZIPs oficiais do IBGE;
3. valida os 35 campos de cada série;
4. executa `scripts/tic_tim/agregar_entorno_apond_csv.py`;
5. executa `scripts/tic_tim/calcular_entorno_apond.py`;
6. valida 7 APONDs, 105 variáveis, 30 distribuições por território e 240 grupos de QA;
7. publica quatro artefatos de saída.

## Execução aprovada

Run `34000432850`: `success`.

Cobertura publicada:

- V050: 174 setores publicados / 33 sem registro;
- V052: 174 setores publicados / 33 sem registro;
- V054: 179 setores publicados / 28 sem registro.

QA final:

- 8 territórios;
- 30 distribuições por território;
- 240 grupos;
- zero erros;
- nenhum valor não numérico;
- desvio máximo de fechamento `1.4210854715202004e-14`.

O Entorno está liberado para incorporação à base estatística v2. A promoção editorial permanece condicionada ao piloto PDF e QA visual.
