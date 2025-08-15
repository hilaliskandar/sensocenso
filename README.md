# Censo 2022 — Plataforma SP (v1.9.3)

Plataforma Streamlit enxuta para análise demográfica (pirâmide etária) por município e por setor censitário, baseada no Parquet local do Censo 2022 de SP.

## Como rodar
```powershell
cd <pasta_do_projeto>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m streamlit run app.py
```

No app, abra a página **10_Piramide_Etaria_SP**.

## Parquet esperado
Atualize o campo no topo da página, por padrão:
```
D:\repo\saida_parquet\base_integrada_final.parquet
```

## Recursos
- Seleção de município e de setor.
- Filtros: **SITUACAO** (Urbana/Rural), **CD_SITUACAO** (decodificado) e **CD_TIPO** (decodificado).
- Pirâmide etária (M/F, 11 faixas).
- Checagem: soma M+F vs **V0001 (Total de pessoas)**, diferença absoluta e %.
- Gráfico de pizza (M/F) para setor e para município.
- Cache de dados com TTL e keepalive opcional.
