# Etapa 11d — Cartografia setorial e prancha do entorno

## Objetivo

Produzir os cinco elementos cartográficos setoriais do inventário visual final diretamente das bases do pipeline e da malha oficial de setores censitários 2022 do IBGE, sem transcrição manual de valores e sem mapas artificiais.

## Elementos

- **M04 — Renovação geracional em escala local.** Usa o CWR setorial `cwr_0_4_por_1000_m1549`. O universo territorial de referência é o checkpoint integrado de 8.073 setores; 7.474 possuem valor corrente válido. Setores sem informação são neutros. Três insets são escolhidos deterministicamente pelos maiores intervalos interquartis municipais do CWR.
- **M06 — Privação sanitário-ambiental associada à moradia.** Usa `PRIV_C3 = 1 - ISAU_C3`. O universo é o mesmo conjunto integrado de 8.073 setores; a edição corrente possui 8.067 valores válidos. O ISAU-C3 combina abastecimento de água, esgotamento, resíduos e drenagem quando ao menos três domínios são observados. Três insets são escolhidos pelas maiores medianas municipais de `PRIV_C3`.
- **M08 — Áreas com necessidades habitacionais combinadas.** Representa `CONVERGENCIA_3_OU_4` preservando o triestado: não convergente, convergente em três dimensões, convergente em quatro dimensões e classificação indeterminada. A edição corrente contém 1.304 setores convergentes; 1.255 é somente referência histórica de QA. Insets usam os maiores percentuais municipais de convergência sobre todos os setores integrados do município.
- **M09 — Estabilidade das áreas de necessidades combinadas sob critério mais restritivo.** Compara P75 e P80 e distingue persistência com mesmo vetor, persistência com composição alterada, não persistência e indeterminação por cobertura. A edição corrente contém 1.016 setores persistentes P75–P80 e 945 com o mesmo vetor; as referências históricas de QA são 959 e 886.
- **M12 — Principais carências da infraestrutura do entorno urbano.** Prancha multipainel com drenagem, calçadas, pavimentação, arborização e iluminação pública, usando o universo completo de 9.087 setores urbanos da etapa 06b. Cada componente possui 8.557 setores com informação válida na edição corrente. Para evitar o colapso de quantis nos componentes com grande massa em zero, cada painel separa explicitamente `0%` e classifica os valores positivos em quatro quantis próprios. Setores sem informação publicada aparecem em cinza.

## Geometria e referência cartográfica

M04, M06, M08 e M09 reutilizam `processed/espacial/base_integrada_espacial_8073.gpkg`, criado na etapa 09 a partir da malha oficial do IBGE. M12 recompõe a geometria dos 9.087 setores da etapa 06b pela mesma malha oficial. Os limites dos 30 municípios vêm de `base_cartografia_municipal_30.gpkg`, validado na etapa 11c. A fonte é SIRGAS 2000 (EPSG:4674) e a renderização usa SIRGAS 2000 / UTM 23S (EPSG:31983).

## Política de edição

Os mapas representam a edição corrente produzida pelo pipeline. As contagens históricas 1.255 setores convergentes P75, 959 persistentes P75–P80 e 886 persistentes com mesmo vetor permanecem referências de QA e não metas de calibração. Os números preliminares 987/800 são obsoletos e não integram esta etapa.

## Saídas

Cada mapa é salvo em PNG e SVG. As bases efetivamente usadas na renderização são persistidas em `outputs/data/11d/`. A geometria completa do M12 também é persistida em GeoPackage e Parquet. O arquivo `outputs/qa/etapa11d_cartografia_setorial.json` registra universos, coberturas, limites de classe, seleção dos insets, referências históricas, deriva corrente e lista de saídas.

## Gates de QA

A etapa falha se deixar de reproduzir os seguintes invariantes correntes: 8.073 setores integrados; 7.474 CWR válidos em M04; 8.067 `PRIV_C3` válidos em M06; 1.304 convergentes P75; 1.016 persistentes P75–P80; 945 persistentes com o mesmo vetor; 9.087 setores no M12 e 8.557 valores válidos em cada um dos cinco componentes do entorno.
