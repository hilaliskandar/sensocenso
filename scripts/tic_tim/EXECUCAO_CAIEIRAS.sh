#!/usr/bin/env bash
set -euo pipefail

: "${DBF:?Defina DBF com o caminho para SP_setores_CD2022.dbf}"
: "${MATRIZ:?Defina MATRIZ com o caminho para a matriz CD_SETOR/APOND de Caieiras}"
OUT_DIR="${OUT_DIR:-outputs/caieiras_apond}"

mkdir -p "$OUT_DIR"

python scripts/tic_tim/validar_config_entorno.py \
  --config config/tic_tim_entorno_regras.json

python scripts/tic_tim/agregar_entorno_apond.py \
  --dbf "$DBF" \
  --matriz "$MATRIZ" \
  --saida "$OUT_DIR/caieiras_entorno_contadores_apond.csv" \
  --qa "$OUT_DIR/caieiras_entorno_contadores_apond.qa.json" \
  --cd-mun 3509007 \
  --n-setores-esperados 207

python scripts/tic_tim/calcular_entorno_apond.py \
  --contadores "$OUT_DIR/caieiras_entorno_contadores_apond.csv" \
  --config config/tic_tim_entorno_regras.json \
  --saida "$OUT_DIR/caieiras_entorno_30_distribuicoes_long.csv" \
  --qa "$OUT_DIR/caieiras_entorno_30_distribuicoes_long.qa.json" \
  --n-aponds-esperadas 7

echo "PASS pipeline Entorno Caieiras"
