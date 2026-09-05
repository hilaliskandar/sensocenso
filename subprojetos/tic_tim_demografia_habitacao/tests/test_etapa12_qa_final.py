import pytest

from tic_tim_demografia.etapa12_qa_final import (
    ETAPAS_ESPERADAS,
    STATUS_ACEITOS,
    validar_sequencia_eventos,
)


def _eventos_validos():
    return [
        {"tipo": "etapa", "etapa": etapa, "status": next(iter(STATUS_ACEITOS[etapa]))}
        for etapa in ETAPAS_ESPERADAS
    ]


def test_sequencia_completa_e_status_aceitos():
    status = validar_sequencia_eventos(_eventos_validos())
    assert list(status) == list(ETAPAS_ESPERADAS)
    assert status["05a"] == "DIAGNOSTICO_ESTRUTURAL"
    assert status["09"] == "OK_COM_DERIVA_EDICAO_E_PENDENCIA_TRANSFORMACAO_MORAN"


def test_sequencia_rejeita_etapa_ausente():
    eventos = [e for e in _eventos_validos() if e["etapa"] != "10b"]
    with pytest.raises(AssertionError, match="Etapas ausentes"):
        validar_sequencia_eventos(eventos)


def test_sequencia_rejeita_status_inesperado():
    eventos = _eventos_validos()
    eventos[-1] = {"tipo": "etapa", "etapa": "11e", "status": "FALHA"}
    with pytest.raises(AssertionError, match="Status inesperado"):
        validar_sequencia_eventos(eventos)


def test_sequencia_rejeita_ultima_ocorrencia_fora_de_ordem():
    eventos = _eventos_validos()
    eventos.append({"tipo": "etapa", "etapa": "07", "status": "OK_COM_DERIVA_EDICAO"})
    with pytest.raises(AssertionError, match="sequência canônica"):
        validar_sequencia_eventos(eventos)
