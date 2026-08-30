from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from ..proveniencia import registrar_arquivo


@dataclass(frozen=True)
class SidraClient:
    timeout: int = 120
    user_agent: str = "tic-tim-demografia/0.1"

    def _get_json(self, url: str) -> Any:
        resposta = requests.get(
            url,
            timeout=self.timeout,
            headers={"User-Agent": self.user_agent},
        )
        resposta.raise_for_status()
        return resposta.json()

    def descritor(self, tabela: int) -> Any:
        url = f"https://apisidra.ibge.gov.br/DescritoresTabela/t/{tabela}"
        return self._get_json(url)

    def valores(self, caminho: str) -> Any:
        caminho = caminho.lstrip("/")
        url = f"https://apisidra.ibge.gov.br/values/{caminho}"
        return self._get_json(url)

    def salvar_json(
        self,
        dados: Any,
        destino: Path,
        *,
        manifesto: Path | None = None,
        origem: str | None = None,
    ) -> None:
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(
            json.dumps(dados, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if manifesto is not None:
            registrar_arquivo(manifesto, destino, origem=origem)


def baixar_descritor_tabela(
    tabela: int,
    destino: Path,
    *,
    manifesto: Path | None = None,
) -> Path:
    cliente = SidraClient()
    url = f"https://apisidra.ibge.gov.br/DescritoresTabela/t/{tabela}"
    dados = cliente.descritor(tabela)
    cliente.salvar_json(dados, destino, manifesto=manifesto, origem=url)
    return destino
