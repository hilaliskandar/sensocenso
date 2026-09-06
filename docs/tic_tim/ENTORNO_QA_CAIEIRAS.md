# Entorno Censo 2022 — Caieiras — QA executado

Estado: `GATE_ENTORNO_QA_INTERNO_OK`

Execução canônica: GitHub Actions run `34000432850`.

Fonte: três agregados oficiais do IBGE de Características urbanísticas do entorno dos domicílios, séries V05000–V05034, V05200–V05234 e V05400–V05434.

Cobertura territorial corrente: 207 setores, 7 APONDs.

Cobertura de registros publicados:

| Universo | Série | Setores com registro | Setores sem registro | Total territorial |
|---|---|---:|---:|---:|
| Domicílios | V050 | 174 | 33 | 207 |
| Moradores | V052 | 174 | 33 | 207 |
| Faces | V054 | 179 | 28 | 207 |

Contagem de setores com registro por APOND:

| APOND | Total | Domicílios | Moradores | Faces |
|---|---:|---:|---:|---:|
| 3509007001 | 47 | 32 | 32 | 33 |
| 3509007002 | 25 | 24 | 24 | 24 |
| 3509007003 | 31 | 26 | 26 | 26 |
| 3509007004 | 28 | 23 | 23 | 26 |
| 3509007005 | 38 | 36 | 36 | 37 |
| 3509007006 | 27 | 26 | 26 | 26 |
| 3509007007 | 11 | 7 | 7 | 7 |

A ausência de linha setorial no arquivo oficial foi tratada como ausência de registro publicado. Nenhum setor sem publicação foi convertido em zero.

QA das distribuições:

- 105 variáveis de Entorno agregadas;
- 30 distribuições por território;
- 7 APONDs + MUNICIPIO = 8 territórios;
- 240 grupos de QA;
- `status = PASS`;
- `erros = []`;
- nenhum valor não numérico publicado nos setores de Caieiras;
- desvio máximo de soma percentual bruto = `1.4210854715202004e-14`;
- desvio máximo de soma percentual no domínio = `1.4210854715202004e-14`.

Artefato do workflow: ID `9979325831`, nome `tic-tim-caieiras-entorno-qa`, SHA-256 do ZIP `e8eb883ce9538013650023ee4b3fc5fbf44169d08c77d944ffe7e10668841e21`.

Próxima etapa: incorporar as distribuições à base normalizada v1 para produzir a v2 e então testar os builders de Caieiras em PDF piloto curto.
