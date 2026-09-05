# TIC–TIM — pipeline reprodutível de demografia, habitação e entorno urbano

Este subprojeto reconstrói de forma auditável o fluxo analítico usado no diagnóstico regional TIC–TIM para 30 municípios: aquisição de fontes oficiais, harmonização 2000–2010–2022, indicadores domiciliares e demográficos, quatro famílias analíticas, sensibilidade P75/P80, validação espacial, sínteses municipais, camadas distributivas, tabelas, gráficos, cartografia e QA final.

## Estado corrente

A edição corrente está fechada e validada nas etapas 00–12. O conteúdo integrado à `main` pelo PR #13 foi validado com 98 testes e execução live completa. O relatório regional correspondente foi aceito editorialmente como versão canônica corrente.

O QA final da edição corrente é:

`OK_REPRODUTIBILIDADE_CORRENTE_COM_RESSALVA_HISTORICA_MORAN`

A ressalva é exclusivamente histórica: ainda falta recuperar a transformação/normalização exata dos pesos usada no artefato computacional antigo para declarar reprodução numérica bit a bit do Moran histórico. Isso não bloqueia nem altera a reprodutibilidade da edição corrente.

## Execução por usuário externo

Pré-requisitos:

- Git;
- Python 3.11;
- acesso à internet para reobter fontes públicas do IBGE/SIDRA nas etapas live;
- espaço em disco compatível com os agregados, malhas e saídas geradas.

Não é necessário Google Drive, credencial privada, arquivo de chat ou caminho específico de máquina.

### Linux/macOS

```bash
git clone https://github.com/hilaliskandar/sensocenso.git
cd sensocenso/subprojetos/tic_tim_demografia_habitacao
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
pytest -q
python scripts/run_pipeline.py --etapa 00
python scripts/run_pipeline.py --etapa implementadas
```

### Windows PowerShell

```powershell
git clone https://github.com/hilaliskandar/sensocenso.git
cd sensocenso\subprojetos\tic_tim_demografia_habitacao
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
pytest -q
python scripts/run_pipeline.py --etapa 00
python scripts/run_pipeline.py --etapa implementadas
```

Para listar as etapas disponíveis:

```bash
python scripts/run_pipeline.py --listar
```

Para executar uma etapa isolada:

```bash
python scripts/run_pipeline.py --etapa 11d
```

O modo padrão é `corrente`. O modo `historico` mantém deliberadamente bloqueadas as partes cuja reprodução numérica integral depende de artefato histórico ainda não recuperado:

```bash
python scripts/run_pipeline.py --modo historico --listar
```

## Armazenamento e portabilidade

Por padrão, os dados e resultados são gravados em `data/` dentro do subprojeto. Para externalizar o armazenamento:

```bash
export TIC_TIM_DATA_ROOT=/dados/tic_tim_demografia
python scripts/run_pipeline.py --etapa implementadas
```

No PowerShell:

```powershell
$env:TIC_TIM_DATA_ROOT = "D:\dados\tic_tim_demografia"
python scripts/run_pipeline.py --etapa implementadas
```

A arquitetura completa está documentada em [`docs/ARQUITETURA_DADOS.md`](docs/ARQUITETURA_DADOS.md). Em síntese:

- `raw/`: fontes obtidas, preservadas com proveniência e hashes;
- `interim/`: intermediários regeneráveis;
- `processed/`: bases analíticas estáveis;
- `outputs/`: tabelas, mapas, gráficos, bases de entrega e QA;
- `metadata/`: manifests, hashes e logs;
- `cache/`: conteúdo descartável e reconstruível.

## Checkpoint territorial canônico

O universo integrado de 8.073 setores depende de um checkpoint territorial histórico explicitamente versionado. Para evitar dependência de arquivo binário externo, o payload é distribuído no próprio repositório como gzip codificado em Base64 e dividido em partes textuais em:

`data/checkpoints/payload_g7f2_b64/`

O runtime concatena as partes, valida o manifesto, os hashes e a cardinalidade e só então materializa o checkpoint. O SHA-256 lógico do checkpoint integrado é:

`72d6490f46c4cef588e2fed7935c69d4d1673c563546f96dfb7683475b13fd6f`

## Etapas implementadas

- **00** — configuração, universo e manifesto inicial;
- **01** — aquisição e congelamento de fontes públicas;
- **02a** — gate semântico SIDRA;
- **02b** — harmonização longitudinal 2000–2010;
- **02c** — incorporação de 2022 e fechamento 30 × 3;
- **03a** — gate semântico das fontes domiciliares;
- **03b** — base domiciliar histórica 2000–2010;
- **03c** — domicílios 2022 e integração temporal;
- **04** — renovação demográfica recente;
- **05a–05e** — privação sanitário-ambiental e ISAU;
- **06a–06b** — atributos do entorno urbano e F3;
- **07** — quatro famílias analíticas;
- **08** — sensibilidade P75/P80;
- **09** — validação espacial;
- **10** — sínteses municipais e correlações;
- **10b** — camadas distributivas de raça/cor, FCU e arranjo doméstico;
- **11a** — tabelas públicas;
- **11b** — gráficos públicos;
- **11c** — cartografia municipal;
- **11d** — cartografia setorial e prancha do entorno;
- **11e** — manifesto visual e QA de cobertura;
- **12** — QA final de reprodutibilidade.

## Princípios de reprodução

1. Usar fontes públicas e versões registradas.
2. Preservar numeradores, denominadores, categorias e flags de cobertura antes de derivar indicadores.
3. Não converter ausência, supressão, sigilo ou não aplicabilidade em zero.
4. Não reconstruir por diferença valores omitidos pelo provedor para proteção estatística.
5. Manter separadas escalas municipal, setorial, moradores, domicílios e faces de logradouro.
6. Tratar variáveis municipais propagadas aos setores somente como contexto compartilhado.
7. Registrar parâmetros, universos efetivos e proveniência de cada etapa.
8. Gerar produtos visuais a partir das bases analíticas, não de imagens finais preexistentes.
9. Não depender de Google Drive, nomes de usuário ou caminhos particulares.
10. Usar produtos históricos apenas como oráculos independentes de QA, nunca como entrada para recalcular o próprio resultado.

## Invariantes da edição corrente

O fechamento validado registra:

- 30 municípios;
- anos 2000, 2010 e 2022;
- 90 linhas na base longitudinal;
- 90 linhas na base domiciliar;
- 9.087 setores urbanos correntes;
- 8.073 setores no universo territorial integrado;
- 177 ilhas na vizinhança Queen;
- 19.314 arestas Queen únicas;
- 304 arestas intermunicipais;
- 1.304 setores convergentes em P75;
- 1.016 setores persistentes P75–P80;
- 945 persistentes com o mesmo vetor;
- 557 setores em FCU e 236 FCU distintas;
- participação regional preta+parda de `0.3974507745638293`;
- cobertura editorial de 25 elementos e 67 arquivos auditados.

As referências históricas 1.255/959/886 permanecem exclusivamente como QA de edição. Os números 987/800 são obsoletos e não devem reaparecer como resultados analíticos.

## Quatro famílias analíticas

- **F1** — dinâmica do estoque domiciliar ocupado e renovação demográfica recente;
- **F2** — privação sanitário-ambiental censitariamente observável;
- **F3** — ausência de atributos selecionados do entorno urbano;
- **F4** — estrutura etária e arranjos domiciliares.

A convergência multidimensional indica presença simultânea de três ou quatro famílias. Não deve ser interpretada automaticamente como déficit, severidade ou prioridade normativa.

## Saídas principais

A execução produz artefatos em `processed/`, `outputs/` e `metadata/`. Entre eles:

- bases municipais e setoriais em CSV/Parquet;
- tabelas públicas e XLSX consolidado;
- gráficos em PNG/SVG com bases CSV;
- mapas municipais e setoriais em PNG/SVG com bases geoespaciais;
- manifestos, hashes e logs de execução;
- `outputs/qa/etapa12_qa_final.json`;
- `outputs/qa/etapa12_resumo_final.md`.

## CI público

Dois workflows específicos exercitam o subprojeto em ambiente limpo do GitHub Actions:

- `TIC-TIM demografia - testes`: instala o pacote, executa `pytest -q` e valida a etapa 00;
- `TIC-TIM demografia live`: instala o pacote, executa os testes e percorre 00–12, publicando QA, bases analíticas e produtos derivados como artefato.

Esses workflows usam apenas permissões de leitura do conteúdo do repositório para a execução do pipeline e não dependem de segredos privados do projeto.

## Falhas transitórias de fonte

A execução live consulta serviços públicos. Timeouts ou indisponibilidades temporárias do SIDRA/IBGE podem causar uma falha de aquisição sem indicar erro metodológico. O pipeline registra a falha e deve ser reexecutado; não substitui silenciosamente a fonte nem imputa valores para atravessar o gate.

## Desenvolvimento e governança

Mudanças metodológicas devem ocorrer em branch própria, acompanhadas de testes e de issue/PR. O fechamento analítico anterior está registrado na issue #12 e no PR #13. O hardening de execução pública está rastreado na issue #14.

Licença do repositório: MIT.
