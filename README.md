# sensocenso

Repositório de ferramentas e pipelines para análise de dados censitários e territoriais.

## Subprojetos

### TIC–TIM — demografia, habitação e entorno urbano

O pipeline reprodutível do diagnóstico regional TIC–TIM está em:

[`subprojetos/tic_tim_demografia_habitacao/`](subprojetos/tic_tim_demografia_habitacao/)

Ele reconstrói, a partir de fontes públicas e de um checkpoint territorial versionado e auditado, as etapas 00–12 do diagnóstico demográfico, habitacional e urbano dos 30 municípios TIC–TIM. A execução não depende de Google Drive, nomes de usuário, caminhos particulares de máquina ou arquivos de sessões anteriores.

Execução mínima em ambiente limpo:

```bash
git clone https://github.com/hilaliskandar/sensocenso.git
cd sensocenso/subprojetos/tic_tim_demografia_habitacao
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest -q
python scripts/run_pipeline.py --etapa implementadas
```

No Windows PowerShell, ative o ambiente com `.\.venv\Scripts\Activate.ps1`.

Consulte o [README específico do subprojeto](subprojetos/tic_tim_demografia_habitacao/README.md) para universos, etapas, artefatos, política de ausência/supressão, execução live e ressalva histórica de Moran.

### Plataforma SP do Censo 2022

A aplicação Streamlit anterior, voltada principalmente à exploração de pirâmides etárias por município e setor censitário, permanece no repositório. Sua documentação detalhada foi preservada em:

[`docs/README_PLATAFORMA_SP_v1.9.3.md`](docs/README_PLATAFORMA_SP_v1.9.3.md)

## Licença

Este repositório é distribuído sob a licença MIT. Consulte [`LICENSE`](LICENSE).
