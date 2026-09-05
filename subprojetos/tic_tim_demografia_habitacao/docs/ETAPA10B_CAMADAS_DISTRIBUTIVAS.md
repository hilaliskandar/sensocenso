# Etapa 10b — camadas distributivas de raça/cor, FCU e arranjo doméstico

## Finalidade

A etapa 10b é uma subdivisão operacional do pipeline criada para explicitar a integração distributiva prevista na issue #12 antes da geração automática de tabelas e mapas. Ela não corresponde a um gate histórico denominado 10b.

As três camadas são **ex post**: qualificam a distribuição social e territorial das condições observadas, mas não entram na formação das famílias F1–F4, não alteram a gravidade físico-urbana, não redefinem o checkpoint de 8.073 setores e não produzem classificação de prioridade.

## Raça/cor

A fonte corrente é o agregado oficial do Censo 2022 por setor censitário, arquivo `Agregados_por_setores_cor_ou_raca_BR.zip`, descoberto no snapshot congelado pela etapa 01.

Variáveis utilizadas:

- `V01317`: branca;
- `V01318`: preta;
- `V01319`: amarela;
- `V01320`: parda;
- `V01321`: indígena.

A análise é restrita aos 9.087 setores do universo urbano corrente. Células protegidas por sigilo permanecem ausentes. As contagens municipais são somadas por categoria e o denominador de raça/cor válida corresponde à soma das cinco categorias publicadas. A participação preta+parda é reconstruída por soma das duas categorias.

## Favelas e Comunidades Urbanas

A etapa parte do índice público congelado para os resultados do universo de Favelas e Comunidades Urbanas, resolve o diretório `Anexos/`, congela também o índice dessa subpasta e seleciona unicamente a planilha oficial de setores em formato XLSX.

O pertencimento à FCU é identificado pelo código setorial. Quando a publicação contém `CD_FCU`, somente códigos efetivos são tratados como FCU e o marcador `.` é explicitamente não-FCU, reproduzindo a regra histórica. Quando a própria tabela oficial já contém exclusivamente setores FCU e não expõe `CD_FCU`, a presença da linha setorial é usada como marcador de pertencimento e essa condição é registrada no QA.

Os denominadores populacional e domiciliar permanecem os mesmos do universo urbano corrente produzido pelo pipeline. `POP_TOTAL` e `DPPO` vêm de `base_isau_priorizacao_2022`, evitando introduzir uma população externa incompatível com as demais etapas.

## Arranjo doméstico

A etapa reutiliza os valores setoriais já produzidos e auditados na etapa 07:

- `V01179`: domicílios sem cônjuge;
- `V01188`: domicílios sem cônjuge cujo responsável é mulher.

O indicador municipal é a razão entre as somas do numerador e do denominador apenas nos setores urbanos em que ambos foram publicados, o denominador é positivo e o numerador não excede o denominador. Ausências e células protegidas não são convertidas em zero.

## Razões de representação

Para cada camada é calculada uma razão relativa à participação do conjunto dos 30 municípios:

`RR = participação municipal / participação agregada dos 30 municípios`

O RR é apenas descritivo. Valores acima de 1 indicam participação municipal superior à referência regional. Os rótulos de ±10% servem para leitura comparativa e não constituem limiar normativo.

## Correlações de Spearman

A etapa calcula, sempre com os 30 municípios quando há dados válidos:

- participação preta+parda × gravidade físico-urbana;
- participação da população urbana em FCU × gravidade físico-urbana;
- participação de responsáveis mulheres entre domicílios sem cônjuge × gravidade físico-urbana.

As referências históricas preservadas no S24 v1.1 são usadas somente como oráculos de QA:

- preta+parda × gravidade: `rho = 0,7569251354`;
- FCU × gravidade: `rho = 0,3475047409`;
- arranjo × gravidade: `rho = -0,5860496198`.

Também são registradas as referências agregadas históricas de 39,7451% para população preta+parda, 5,5308% para população urbana em FCU e cobertura setorial de 95,9393% para V01179/V01188. Divergências de edição são documentadas e não corrigidas artificialmente.

## Saídas

A etapa produz:

- `processed/municipal/base_camadas_distributivas_2022.csv`;
- `processed/municipal/base_camadas_distributivas_2022.parquet`;
- `outputs/qa/etapa10b_correlacoes_distributivas.csv`;
- `outputs/qa/etapa10b_camadas_distributivas.json`.

O JSON de QA registra URLs efetivamente resolvidas, arquivos brutos, regra de marcação FCU, universo, coberturas, referências regionais correntes, comparação com o fechamento histórico e correlações.

## Relação com a etapa 11

A etapa 11 somente deverá gerar tabelas e mapas a partir das bases produzidas pelo próprio pipeline. As camadas distributivas poderão aparecer em tabelas, gráficos ou mapas descritivos, mas deverão permanecer separadas das quatro famílias analíticas e da gravidade físico-urbana.