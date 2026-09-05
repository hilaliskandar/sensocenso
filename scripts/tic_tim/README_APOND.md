# Pipeline TIC-TIM — Cadernos APOND

Este diretório contém o pipeline reprodutível mínimo para reconstruir o bloco de Características Urbanísticas do Entorno dos Cadernos APOND, começando por Caieiras (CD_MUN 3509007).

## Ordem de execução

1. `agregar_entorno_apond.py`
   - lê o DBF estadual de setores de forma iterativa;
   - mantém apenas os setores presentes na matriz Setor→APOND do município;
   - exige 207 setores para Caieiras por padrão;
   - agrega os contadores `V050xx`, `V052xx` e `V054xx` por APOND;
   - acrescenta a linha `MUNICIPIO` pela soma das APONDs;
   - não calcula percentuais nem aplica domínios;
   - produz CSV de contadores e QA JSON.

2. `calcular_entorno_apond.py`
   - lê o CSV de contadores;
   - usa `config/tic_tim_entorno_regras.json` como fonte declarativa da semântica E01–E10;
   - calcula percentual bruto com todas as categorias observadas;
   - calcula percentual no domínio aplicável apenas com categorias marcadas como aplicáveis;
   - mantém percentual de domínio vazio para categorias fora do domínio;
   - valida 30 distribuições por território, fechamento percentual bruto e fechamento do domínio aplicável;
   - produz CSV longo e QA JSON.

3. Integração estatística
   - preservar `TIC_TIM_Censo2022_Caieiras_Tabelas_Normalizadas_APOND_168_v1.xlsx` como artefato imutável do gate de normalização;
   - incorporar o Entorno validado em nova base `..._168_Entorno_v2.xlsx`;
   - não substituir ausência/não aplicabilidade por zero.

4. Caderno
   - construir primeiro um PDF piloto curto com capa, metodologia, diretório A01–A07 e poucas variáveis representativas;
   - executar QA visual e estatístico;
   - somente após aceite gerar os Volumes I–III completos.

## Exemplo de execução

```bash
python scripts/tic_tim/agregar_entorno_apond.py \
  --dbf SP_setores_CD2022.dbf \
  --matriz caieiras_setor_apond.csv \
  --saida caieiras_entorno_contadores_apond.csv

python scripts/tic_tim/calcular_entorno_apond.py \
  --contadores caieiras_entorno_contadores_apond.csv \
  --config config/tic_tim_entorno_regras.json \
  --saida caieiras_entorno_30_distribuicoes_long.csv \
  --n-aponds-esperadas 7
```

## Gate

Enquanto os scripts não forem executados sobre o DBF canônico e seus QAs não retornarem `PASS`, o estado deve ser registrado como `PIPELINE_ENTORNO_CODIFICADO_PENDENTE_EXECUCAO`. A presença do código não equivale ao fechamento do gate estatístico.
