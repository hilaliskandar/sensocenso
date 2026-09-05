"""Compatibilidade para o universo integrado canônico TIC-TIM.

O runtime deve consumir o checkpoint local e imutável Gate18G7F2. O módulo
histórico, que sabe ler os workbooks G7E/G11, permanece disponível apenas para
materialização/auditoria e para os testes de compatibilidade; ele não é usado
como mecanismo de download durante a execução normal da pipeline.
"""

from __future__ import annotations

from pathlib import Path

from . import universo_integrado_legacy as _legacy
from .checkpoint_canonico import CHECKPOINT_FILENAME, carregar_checkpoint_canonico_local
from .checkpoint_compactado import (
    caminho_payload_versionado,
    carregar_checkpoint_compactado_versionado,
)

# API histórica preservada para testes e utilitários de auditoria.
G7E_FILENAME = _legacy.G7E_FILENAME
G7E_SHEET_ID = _legacy.G7E_SHEET_ID
G7E_EXPORT_URL = _legacy.G7E_EXPORT_URL
G7E_DIAGNOSTICO_FILENAME = _legacy.G7E_DIAGNOSTICO_FILENAME
G7E_DOWNLOAD_DIAGNOSTICO_FILENAME = _legacy.G7E_DOWNLOAD_DIAGNOSTICO_FILENAME
G11_FILENAME = _legacy.G11_FILENAME
G11_SHEET_ID = _legacy.G11_SHEET_ID
G11_EXPORT_URL = _legacy.G11_EXPORT_URL
G11_DOWNLOAD_DIAGNOSTICO_FILENAME = _legacy.G11_DOWNLOAD_DIAGNOSTICO_FILENAME
G7E_COMPOSICAO_MACRO_CANONICA = _legacy.G7E_COMPOSICAO_MACRO_CANONICA

_detectar_linha_cabecalho = _legacy._detectar_linha_cabecalho
_composicao_macrotipos = _legacy._composicao_macrotipos
_extrair_universo = _legacy._extrair_universo


def carregar_universo_integrado_canonico(
    raw_root: str | Path,
    *,
    esperado: int = 8073,
):
    """Carrega o Gate18G7F2 sem depender de acesso de rede no runtime.

    A prioridade é: fonte histórica local explicitamente preparada; checkpoint
    CSV local no diretório de trabalho; payload compacto versionado no repositório.
    Nenhum desses caminhos realiza download durante a execução normal.
    """
    raw_path = Path(raw_root)
    fonte_historica_local = raw_path / "checkpoints" / G7E_FILENAME
    if fonte_historica_local.exists() and fonte_historica_local.stat().st_size > 0:
        return _legacy.carregar_universo_integrado_canonico(raw_path, esperado=esperado)

    checkpoint_local = raw_path / "checkpoints" / CHECKPOINT_FILENAME
    if checkpoint_local.exists() and checkpoint_local.stat().st_size > 0:
        return carregar_checkpoint_canonico_local(raw_path, esperado=esperado)

    if caminho_payload_versionado().exists():
        return carregar_checkpoint_compactado_versionado(esperado=esperado)

    return carregar_checkpoint_canonico_local(raw_path, esperado=esperado)
