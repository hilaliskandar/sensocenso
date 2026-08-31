# Arquitetura despersonalizada de dados e resultados

O pipeline não depende de Google Drive, nomes de usuário, caminhos locais específicos ou pastas pessoais. Toda entrada persistente e todo resultado produzido são resolvidos a partir da raiz do subprojeto e da configuração `config/paths.yml`.

Opcionalmente, a variável de ambiente `TIC_TIM_DATA_ROOT` pode apontar o armazenamento pesado para qualquer volume local, servidor, contêiner ou diretório montado. O código permanece inalterado.

## Estrutura operacional

```text
<DATA_ROOT>/
├── raw/                         # cópia imutável das fontes obtidas
│   ├── ibge/
│   │   ├── censo_2000/
│   │   │   └── sidra/
│   │   ├── censo_2010/
│   │   │   ├── sidra/
│   │   │   └── sinopse/
│   │   └── censo_2022/
│   │       ├── agregados_setores/
│   │       ├── entorno/
│   │       ├── malhas/
│   │       └── fcu/
│   └── outros/
├── external/                    # fontes manuais não baixáveis automaticamente
│   └── README.md                # instruções, origem e checksum esperado
├── interim/                     # resultados temporários entre etapas
│   ├── longitudinal/
│   ├── setores_2022/
│   ├── entorno/
│   └── espacial/
├── processed/                   # bases analíticas finais, estáveis e reutilizáveis
│   ├── municipal/
│   ├── setorial/
│   ├── espacial/
│   └── indicadores/
├── outputs/
│   ├── tables/                  # tabelas prontas para publicação
│   ├── maps/                    # mapas e pranchas
│   ├── data/                    # exportações CSV/Parquet/GPKG
│   ├── qa/                      # relatórios de QA e regressão
│   └── reports/                 # artefatos editoriais gerados
├── metadata/
│   ├── manifests/               # proveniência por execução e por fonte
│   ├── hashes/                  # checksums das fontes e produtos-chave
│   └── logs/                    # logs estruturados de execução
└── cache/                       # conteúdo descartável e reconstruível
```

## Regras de persistência

### `raw/`

É somente leitura após a obtenção. O pipeline nunca corrige um arquivo bruto em lugar. Cada arquivo deve ter registro de URL/origem, data de obtenção, tamanho e SHA-256. Se a fonte oficial mudar, a nova obtenção recebe nova entrada de manifesto; a anterior não é silenciosamente substituída.

### `external/`

Serve apenas para uma fonte que não possa ser reobtida automaticamente. O pipeline deve parar com mensagem explícita caso um arquivo obrigatório esteja ausente. Nenhum caminho de Drive, pasta de usuário ou ID pessoal pode constituir requisito de execução.

### `interim/`

Contém produtos intermediários regeneráveis. Pode ser apagado e reconstruído do `raw/`. Não constitui fonte de verdade.

### `processed/`

Contém bases analíticas finais de cada etapa, já com esquema documentado e QA aprovado. As etapas posteriores devem consumir preferencialmente `processed/`, não arquivos soltos de sessões anteriores.

### `outputs/`

Contém exclusivamente produtos derivados do pipeline: tabelas, mapas, bases de entrega e artefatos editoriais. Nenhum resultado é usado como entrada para recalcular o próprio indicador que o originou.

### `metadata/`

É a trilha de auditoria: manifests, hashes e logs. Uma execução reproduzível deve permitir identificar exatamente quais arquivos e parâmetros geraram cada produto.

### `cache/`

Pode ser removido a qualquer momento sem perda de informação substantiva.

## Portabilidade

A configuração padrão usa `subprojetos/tic_tim_demografia_habitacao/data` como raiz. Para armazenar dados fora do repositório:

```bash
export TIC_TIM_DATA_ROOT=/dados/tic_tim_demografia
python scripts/run_pipeline.py --etapa 00
```

No Windows PowerShell:

```powershell
$env:TIC_TIM_DATA_ROOT = "D:\dados\tic_tim_demografia"
python scripts/run_pipeline.py --etapa 00
```

Em contêineres e CI, basta montar um volume e definir a mesma variável.

## Regra de despersonalização

São proibidos no código e na configuração versionada:

- caminhos como `/home/nome`, `C:\Users\NOME`, `/content/drive/MyDrive`;
- IDs ou URLs do Google Drive usados como dependência de execução;
- nomes de máquinas, contas pessoais ou pastas locais particulares;
- leitura implícita de arquivos fora da raiz configurada;
- dependência de resultados produzidos manualmente em chats anteriores.

O histórico do projeto pode ser usado apenas para estabelecer valores de QA e documentação metodológica. A execução produtiva deve partir de fontes públicas ou de insumos explicitamente documentados em `external/`.
