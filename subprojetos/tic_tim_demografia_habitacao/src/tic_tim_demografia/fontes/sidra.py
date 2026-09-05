from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import requests

from ..proveniencia import registrar_arquivo


BASE_VALUES = "https://apisidra.ibge.gov.br/values"
BASE_DESCRIPTOR = "https://apisidra.ibge.gov.br/DescritoresTabela"


def _lista_segmento(valores: Sequence[str | int] | str | int) -> str:
    if isinstance(valores, (str, int)):
        return str(valores)
    return ",".join(str(v) for v in valores)


def construir_caminho_sidra(
    *,
    tabela: int,
    nivel_territorial: int,
    localidades: Sequence[str | int] | str,
    variaveis: Sequence[str | int] | str = "allxp",
    periodos: Sequence[str | int] | str = "all",
    classificacoes: Mapping[int | str, Sequence[str | int] | str] | None = None,
    cabecalho: bool = True,
    formato: str = "a",
    decimais: str = "m",
) -> str:
    """Constrói caminho oficial `/values` do SIDRA de forma determinística."""
    partes = [
        f"t/{int(tabela)}",
        f"n{int(nivel_territorial)}/{_lista_segmento(localidades)}",
        f"v/{_lista_segmento(variaveis)}",
        f"p/{_lista_segmento(periodos)}",
    ]
    for classificacao, categorias in sorted((classificacoes or {}).items(), key=lambda x: int(x[0])):
        partes.append(f"c{int(classificacao)}/{_lista_segmento(categorias)}")
    partes.extend([f"h/{'y' if cabecalho else 'n'}", f"f/{formato}", f"d/{decimais}"])
    return "/".join(partes)


def dividir_lotes(itens: Sequence[str], tamanho: int) -> list[list[str]]:
    if tamanho <= 0:
        raise ValueError("tamanho do lote deve ser positivo")
    return [list(itens[i : i + tamanho]) for i in range(0, len(itens), tamanho)]


@dataclass(frozen=True)
class SidraClient:
    """Cliente resiliente para o webservice SIDRA.

    O serviço público pode apresentar indisponibilidades transitórias. O cliente
    usa timeout de conexão curto, timeout de leitura mais amplo e repetição com
    espera exponencial apenas para erros de rede e respostas 429/5xx. Erros 4xx
    de consulta não são mascarados por tentativas sucessivas.
    """

    connect_timeout: int = 20
    read_timeout: int = 180
    tentativas: int = 4
    backoff_inicial: float = 2.0
    user_agent: str = "tic-tim-demografia/0.1 (+pipeline-reprodutivel)"

    def _get_json(self, url: str) -> Any:
        ultimo_erro: Exception | None = None
        for tentativa in range(1, self.tentativas + 1):
            try:
                resposta = requests.get(
                    url,
                    timeout=(self.connect_timeout, self.read_timeout),
                    headers={"User-Agent": self.user_agent, "Accept": "application/json"},
                )
                if resposta.status_code == 429 or resposta.status_code >= 500:
                    resposta.raise_for_status()
                resposta.raise_for_status()
                return resposta.json()
            except (requests.ConnectionError, requests.Timeout) as exc:
                ultimo_erro = exc
            except requests.HTTPError as exc:
                ultimo_erro = exc
                status = exc.response.status_code if exc.response is not None else None
                if status is not None and 400 <= status < 500 and status != 429:
                    raise
            except requests.JSONDecodeError:
                raise

            if tentativa < self.tentativas:
                espera = self.backoff_inicial * (2 ** (tentativa - 1))
                time.sleep(espera)

        raise RuntimeError(
            f"SIDRA indisponível após {self.tentativas} tentativas para {url}: {ultimo_erro}"
        ) from ultimo_erro

    def descritor(self, tabela: int) -> Any:
        return self._get_json(f"{BASE_DESCRIPTOR}/t/{tabela}")

    def valores(self, caminho: str) -> Any:
        return self._get_json(f"{BASE_VALUES}/{caminho.lstrip('/')}")

    def salvar_json(
        self,
        dados: Any,
        destino: Path,
        *,
        manifesto: Path | None = None,
        origem: str | None = None,
        sobrescrever: bool = False,
    ) -> None:
        if destino.exists() and not sobrescrever:
            raise FileExistsError(
                f"Arquivo bruto SIDRA já existe e não será substituído silenciosamente: {destino}"
            )
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
    url = f"{BASE_DESCRIPTOR}/t/{tabela}"
    dados = cliente.descritor(tabela)
    cliente.salvar_json(dados, destino, manifesto=manifesto, origem=url)
    return destino


def baixar_valores_municipais_em_lotes(
    *,
    tabela: int,
    codigos_municipais: Sequence[str],
    destino_dir: Path,
    periodos: Sequence[str | int] | str,
    variaveis: Sequence[str | int] | str = "allxp",
    classificacoes: Mapping[int | str, Sequence[str | int] | str] | None = None,
    tamanho_lote: int = 10,
    manifesto: Path | None = None,
    cliente: SidraClient | None = None,
) -> list[Path]:
    """Baixa respostas SIDRA municipais em lotes pequenos e auditáveis."""
    cliente = cliente or SidraClient()
    codigos = [str(c) for c in codigos_municipais]
    saidas: list[Path] = []
    for numero, lote in enumerate(dividir_lotes(codigos, tamanho_lote), start=1):
        caminho = construir_caminho_sidra(
            tabela=tabela,
            nivel_territorial=6,
            localidades=lote,
            variaveis=variaveis,
            periodos=periodos,
            classificacoes=classificacoes,
            cabecalho=True,
            formato="a",
            decimais="m",
        )
        url = f"{BASE_VALUES}/{caminho}"
        dados = cliente.valores(caminho)
        destino = destino_dir / f"t{tabela}_lote_{numero:02d}.json"
        cliente.salvar_json(dados, destino, manifesto=manifesto, origem=url)
        saidas.append(destino)
    return saidas
