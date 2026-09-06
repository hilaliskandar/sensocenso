# TIC-TIM — Caieiras — pipeline APOND / Entorno

## Estado corrente

`GATE_ENTORNO_QA_INTERNO_OK`

O pipeline do Entorno de Caieiras foi executado com sucesso no GitHub Actions, run `34000432850`, sobre os três agregados oficiais específicos de Entorno do Censo Demográfico 2022 do IBGE.

## Território auditado

Caieiras possui 207 setores distribuídos em 7 APONDs:

- 3509007001: 47 setores
- 3509007002: 25 setores
- 3509007003: 31 setores
- 3509007004: 28 setores
- 3509007005: 38 setores
- 3509007006: 27 setores
- 3509007007: 11 setores

A composição Setor→APOND está versionada em `data/tic_tim/caieiras_setor_apond_207.csv`.

## Fonte oficial do Entorno

Diretório IBGE:

`Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios_Caracteristicas_urbanisticas_do_entorno_dos_domicilios/Agregados_por_Setor_csv`

Arquivos utilizados:

- `Agregados_por_setores_entorno_domicílios_BR.zip` — V05000–V05034;
- `Agregados_por_setores_entorno_moradores_BR.zip` — V05200–V05234;
- `Agregados_por_setores_entorno_faces_BR.zip` — V05400–V05434.

São 105 contadores publicados no total.

## Regra metodológica

1. Filtrar os setores pertencentes à composição territorial corrente.
2. Preservar setor sem registro publicado como ausência de registro, nunca como zero.
3. Somar contadores publicados por APOND.
4. Reconstruir o consolidado municipal pela soma dos contadores das APONDs.
5. Somente depois calcular percentuais.
6. Preservar percentual bruto e percentual no domínio aplicável.
7. Não calcular média de percentuais setoriais.

As regras de domínio E01–E10 estão em `config/tic_tim_entorno_regras.json`.

## Cobertura efetivamente publicada

Na execução aprovada:

- Domicílios V050: 174 setores com registro publicado; 33 sem registro publicado.
- Moradores V052: 174 setores com registro publicado; 33 sem registro publicado.
- Faces V054: 179 setores com registro publicado; 28 sem registro publicado.

Todos os sete APONDs possuem registros publicados nos três universos.

Não foram encontrados valores publicados não numéricos nos 105 campos para os setores de Caieiras.

## QA aprovado

A execução produziu:

- 7 APONDs + linha MUNICIPIO = 8 territórios;
- 30 distribuições por território;
- 240 grupos de QA;
- zero erros de fechamento;
- desvio máximo da soma dos percentuais brutos: `1.4210854715202004e-14`;
- desvio máximo da soma dos percentuais no domínio: `1.4210854715202004e-14`.

Artefato do run: `tic-tim-caieiras-entorno-qa`, artifact ID `9979325831`, SHA-256 do ZIP `e8eb883ce9538013650023ee4b3fc5fbf44169d08c77d944ffe7e10668841e21`.

## Scripts correntes

- `scripts/tic_tim/agregar_entorno_apond_csv.py`: agregação oficial a partir dos três CSVs do Entorno.
- `scripts/tic_tim/calcular_entorno_apond.py`: cálculo das 30 distribuições e QA dos percentuais.
- `scripts/tic_tim/agregar_entorno_apond.py`: rota DBF anterior, mantida apenas como referência/fallback; não é a fonte canônica corrente do Entorno.
- `.github/workflows/tic_tim_caieiras_entorno_qa.yml`: execução reproduzível no GitHub Actions.

## Próximo gate

O Entorno já não bloqueia a continuidade estatística. O próximo gate é:

1. incorporar as 30 distribuições auditadas à base normalizada de 168 variáveis, gerando a base v2;
2. parametrizar os builders para Caieiras, A01–A07 em bloco único;
3. gerar um PDF piloto curto com cartografia real;
4. executar QA visual e estatístico do piloto;
5. somente então gerar Volumes I–III e o consolidado.

O PR permanece em rascunho até a incorporação à base v2 e aprovação do piloto editorial/cartográfico.
