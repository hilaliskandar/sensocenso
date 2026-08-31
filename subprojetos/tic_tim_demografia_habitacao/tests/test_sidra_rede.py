import requests
import pytest

from tic_tim_demografia.fontes import sidra


class RespostaFake:
    def __init__(self, dados=None, status_code=200):
        self._dados = dados if dados is not None else {"ok": True}
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            erro = requests.HTTPError(f"HTTP {self.status_code}")
            erro.response = self
            raise erro

    def json(self):
        return self._dados


def test_cliente_repete_timeout_e_recupera(monkeypatch):
    chamadas = []
    esperas = []

    def fake_get(url, **kwargs):
        chamadas.append((url, kwargs["timeout"]))
        if len(chamadas) < 3:
            raise requests.ConnectTimeout("indisponibilidade transitória")
        return RespostaFake({"ok": True})

    monkeypatch.setattr(sidra.requests, "get", fake_get)
    monkeypatch.setattr(sidra.time, "sleep", lambda segundos: esperas.append(segundos))

    cliente = sidra.SidraClient(
        connect_timeout=3,
        read_timeout=9,
        tentativas=4,
        backoff_inicial=0.5,
    )
    assert cliente._get_json("https://exemplo.invalid") == {"ok": True}
    assert len(chamadas) == 3
    assert all(timeout == (3, 9) for _, timeout in chamadas)
    assert esperas == [0.5, 1.0]


def test_cliente_nao_repete_erro_400(monkeypatch):
    chamadas = []

    def fake_get(url, **kwargs):
        chamadas.append(url)
        return RespostaFake(status_code=400)

    monkeypatch.setattr(sidra.requests, "get", fake_get)
    monkeypatch.setattr(
        sidra.time,
        "sleep",
        lambda _segundos: pytest.fail("erro 400 não deve disparar backoff"),
    )

    cliente = sidra.SidraClient(tentativas=4)
    with pytest.raises(requests.HTTPError):
        cliente._get_json("https://exemplo.invalid")
    assert len(chamadas) == 1


def test_cliente_falha_com_mensagem_apos_tentativas(monkeypatch):
    chamadas = []

    def fake_get(url, **kwargs):
        chamadas.append(url)
        raise requests.ConnectTimeout("sem conexão")

    monkeypatch.setattr(sidra.requests, "get", fake_get)
    monkeypatch.setattr(sidra.time, "sleep", lambda _segundos: None)

    cliente = sidra.SidraClient(tentativas=3, backoff_inicial=0)
    with pytest.raises(RuntimeError, match="SIDRA indisponível após 3 tentativas"):
        cliente._get_json("https://exemplo.invalid")
    assert len(chamadas) == 3
