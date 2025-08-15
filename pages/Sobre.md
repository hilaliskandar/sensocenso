# Sobre o SensoCenso

## Introdução

O SensoCenso é um sistema de análise e visualização de dados do Censo Demográfico 2022 do IBGE, desenvolvido em Python/Streamlit. Ele permite explorar microdados censitários, com foco em pirâmides etárias, composição domiciliar e recortes territoriais, utilizando metodologias e dicionários oficiais do IBGE.

---

## Metodologia e Fontes

O sistema utiliza os microdados do Censo 2022, que são compostos por dois instrumentos principais:

- **Questionário do Universo**: aplicado a 100% dos domicílios, com 26 perguntas básicas sobre moradia e perfil dos moradores.
- **Questionário da Amostra**: aplicado a cerca de 11% dos domicílios, com 77 questões adicionais sobre renda, escolaridade, migração, etc.

As variáveis, códigos e categorias seguem os dicionários oficiais do IBGE e SEADE. Recomenda-se sempre consultar as Notas Metodológicas e Dicionários de Dados para correta interpretação dos resultados.

Referências completas e links para questionários, dicionários e notas técnicas estão disponíveis ao final desta página.

---

## Algoritmo e Processamento dos Dados

O processamento dos dados no SensoCenso segue as seguintes etapas principais:

### 1. Leitura dos Dados
- Os dados são lidos a partir de arquivos Parquet, utilizando a biblioteca DuckDB para alta performance.
- O script identifica automaticamente as colunas de UF (estado), município, setor censitário e outras chaves geográficas, mesmo que os nomes variem entre diferentes bases (ex: `CD_MUN`, `CODIGO_DO_MUNICIPIO`, etc).

### 2. Padronização de Colunas
- Funções como `_rename_by_alias` garantem que todas as colunas relevantes sejam renomeadas para um padrão único, facilitando o processamento posterior.
- Códigos numéricos são normalizados para garantir consistência (ex: remoção de zeros à esquerda, conversão para string).

### 3. Decodificação de Variáveis
- Variáveis categóricas (ex: situação do setor, tipo de setor) são decodificadas para texto descritivo, usando dicionários como `SITUACAO_DET_MAP` e `TIPO_MAP`.
- Caso falte alguma coluna descritiva, ela é criada a partir do código correspondente.

### 4. Seleção e Transformação de Colunas Etárias
- O algoritmo identifica automaticamente as colunas de população por sexo e faixa etária, mesmo que os nomes variem.
- As colunas são reorganizadas e transformadas do formato "wide" (uma coluna por faixa) para "long" (uma linha por faixa), facilitando a análise e visualização.

### 5. Agregação e Saídas
- As funções permitem agrupar os dados por diferentes níveis geográficos (setor, município, estado) e sumarizar por sexo, faixa etária e outras dimensões.
- O resultado pode ser utilizado para gerar pirâmides etárias, mapas, tabelas e outros tipos de visualização.

---

## Decisões de Projeto
- **Flexibilidade**: O código aceita diferentes formatos e nomes de variáveis, tornando-o robusto para diferentes versões dos microdados.
- **Eficiência**: O uso de DuckDB e operações vetorizadas do Pandas garante performance mesmo com grandes volumes de dados.
- **Transparência**: Todas as transformações são documentadas e baseadas em dicionários oficiais.

---

## Referências e Documentação
- IBGE. Censo Demográfico 2022: conceitos e métodos. https://www.ibge.gov.br/estatisticas/sociais/populacao/22827-censo-demografico-2022.html
- SEADE. Dicionário de dados: Censo Demográfico 2022 – Domicílios. https://repositorio.seade.gov.br/
- Questionário Básico (Universo): https://anda.ibge.gov.br/np_download/censo2022/questionario_basico_completo_CD2022_atualizado_20220906.pdf
- Notas Metodológicas IBGE: https://www.ibge.gov.br/estatisticas/sociais/populacao/22827-censo-demografico-2022.html
- IPUMS International: https://international.ipums.org/

---

Para dúvidas metodológicas ou sugestões, consulte a documentação oficial ou entre em contato com a equipe do projeto.

---

## Indicadores Demográficos: Cálculo, Leitura e Importância

Esta seção apresenta um guia prático sobre quais variáveis do Censo 2022 utilizar, como calcular os principais indicadores demográficos e como interpretá-los para subsidiar políticas públicas urbanas.

### 1) Variáveis do Censo 2022 (nível municipal)

- **População residente por idade simples e sexo** (0, 1, 2, …, 100+): permite agregação em faixas etárias relevantes (0–14, 15–64, 60+/65+).
- **Mulheres de 15–49 anos por idade**: base para indicadores de fecundidade.
- **Crianças de 0 ano**: proxy de nascidos vivos no último ano (quando não há SINASC).

### 2) Principais Indicadores e Fórmulas

| Indicador | Fórmula | O que representa | Leitura prática |
|-----------|---------|------------------|-----------------|
| **Razão de Dependência Total (RDT)** | `RDT = ((Pop 0–14 + Pop 65+) / Pop 15–64) × 100` | Quantas pessoas em idades “dependentes” existem para cada 100 em idade potencialmente ativa | Quanto maior, maior pressão sobre renda, serviços e redes de cuidado |
| **Dependência Jovem (RDJ)** | `RDJ = (Pop 0–14 / Pop 15–64) × 100` | Dependência gerada pelos mais jovens | Alta → pressão por creches, escolas, saúde infantil |
| **Dependência Idosa (RDI)** | `RDI = (Pop 65+ / Pop 15–64) × 100` | Dependência gerada pelos idosos | Alta → pressão por atenção básica, cuidados de longa duração |
| **Índice de Envelhecimento (IE)** | `IE(60+) = (Pop 60+ / Pop 0–14) × 100` ou `IE(65+) = (Pop 65+ / Pop 0–14) × 100` | Relação entre idosos e crianças | >100: mais idosos que crianças |
| **Taxa Bruta de Natalidade (TBN)** | `TBN = (Nascidos Vivos no ano / Pop média do ano) × 1.000` | Nascimentos por mil habitantes | Use SINASC para o numerador |
| **TBN (proxy via Censo)** | `TBN_proxy = (Pop idade 0 / Pop Total) × 1.000` | Aproxima os nascimentos do último ano | Limitações: não captura óbitos infantis/migração |

**Notas:**
- Use população em idade simples para formar grupos etários.
- Prefira 65+ para comparações internacionais; 60+ para políticas nacionais.
- Sempre declare o corte etário utilizado.

### 3) Passo a passo de cálculo

1. Agregue idades do Censo 2022 para cada município:
	- `pop_0_14 = soma(idades 0..14)`
	- `pop_15_64 = soma(idades 15..64)`
	- `pop_60p = soma(idades 60..100+)` e/ou `pop_65p = soma(idades 65..100+)`
	- `pop_total = soma(0..100+)`
	- `pop_idade0 = idade == 0`
2. Aplique as fórmulas para RDT, RDJ, RDI, IE e TBN_proxy.
3. Para TBN oficial, use nascidos_vivos do SINASC.
4. Valide resultados e reporte casas decimais coerentes.

### 4) Interpretação e faixas de referência

- **RDT**: 0–50 (baixa), 50–80 (moderada), >80 (alta dependência)
- **IE**: <50 (população jovem), 50–100 (transição), >100 (envelhecida)
- **TBN**: <10 (baixa), 10–15 (baixa-moderada), >15 (elevada)

### 5) Implicações para políticas públicas urbanas

- **Dependência jovem alta**: foco em educação, mobilidade escolar, espaço público e habitação para famílias jovens.
- **Dependência idosa alta**: aging-in-place, saúde, mobilidade acessível, uso do solo para serviços de proximidade.
- **IE > 100 e TBN baixa**: redimensionamento de infraestrutura, retenção de jovens, ajuste fiscal e habitação assistida.
- **TBN alta e RDJ elevada**: expansão escolar, saneamento, planejamento urbano preventivo.

### 6) Boas práticas e limitações

- Declare sempre o corte etário utilizado.
- TBN via Censo é apenas um proxy; prefira SINASC para análises robustas.
- Considere migração e possíveis erros de idade.
- Mantenha consistência metodológica ao comparar anos diferentes.

---

## Links úteis e Notas Técnicas do IBGE

- Portal do Censo 2022 IBGE: https://www.ibge.gov.br/estatisticas/sociais/populacao/22827-censo-demografico-2022.html
- Notas Metodológicas: https://www.ibge.gov.br/estatisticas/sociais/populacao/22827-censo-demografico-2022.html?edicao=42997&t=publicacoes
- Nota Metodológica nº 01/2023: https://www.ibge.gov.br/estatisticas/download/22827-censo-demografico-2022/42997-2023-01-nota-metodologica-censo-2022.html
- Nota Metodológica nº 02/2025: https://www.ibge.gov.br/estatisticas/download/22827-censo-demografico-2022/42998-2025-02-nota-metodologica-censo-2022.html
- Dicionários de Dados: https://repositorio.seade.gov.br/ e https://www.ibge.gov.br/estatisticas/download/22827-censo-demografico-2022/42999-dicionario-de-dados-censo-2022.html
- Questionário Básico: https://anda.ibge.gov.br/np_download/censo2022/questionario_basico_completo_CD2022_atualizado_20220906.pdf
- Microdados: https://www.ibge.gov.br/estatisticas/sociais/populacao/22827-censo-demografico-2022.html?edicao=42997&t=microdados

---

**Checklist operacional:**
1. Extrair do Censo 2022: população por idade simples e mulheres 15–49 por idade.
2. Agregar 0–14, 15–64 e 60+/65+.
3. Calcular: RDT, RDJ, RDI, IE e TBN_proxy.
4. Se disponível, substituir TBN_proxy por TBN (SINASC).
5. Interpretar à luz de migração, rede escolar/saúde e estoque habitacional.
