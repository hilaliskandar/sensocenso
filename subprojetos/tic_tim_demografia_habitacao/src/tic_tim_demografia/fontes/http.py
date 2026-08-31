from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from ..proveniencia import registrar_arquivo


@dataclass(frozen=True)
class HttpClient:
    timeout: int = 180
    user_agent: str = "tic-tim-demografia/0.1"

    def _get(self, url: str, *, stream: bool = False) -> requests.Response:
        resposta = requests.get(
            url,
            timeout=self.timeout,
            stream=stream,
            headers={"User-Agent": self.user_agent},
        )
        resposta.raise_for_status()
        return resposta

    def salvar_texto(
        self,
        url: str,
        destino: Path,
        *,
        manifesto: Path | None = None,
        encoding: str = "utf-8",
    ) -> Path:
        resposta = self._get(url)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(resposta.text, encoding=encoding)
        if manifesto is not None:
            registrar_arquivo(manifesto, destino, origem=resposta.url)
        return destino

    def baixar_arquivo(
        self,
        url: str,
        destino: Path,
        *,
        manifesto: Path | None = None,
        sobrescrever: bool = False,
    ) -> Path:
        if destino.exists() and not sobrescrever:
            raise FileExistsError(
                f"Arquivo bruto já existe e não será substituído silenciosamente: {destino}"
            )

        resposta = self._get(url, stream=True)
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporario = destino.with_suffix(destino.suffix + ".part")
        with temporario.open("wb") as f:
            for chunk in resposta.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
        temporario.replace(destino)

        if manifesto is not None:
            registrar_arquivo(manifesto, destino, origem=resposta.url)
        return destino


def listar_links_indice(url: str, *, cliente: HttpClient | None = None) -> list[str]:
    """Lista links absolutos de uma página de índice HTTP/FTP publicada pelo IBGE."""
    cliente = cliente or HttpClient()
    resposta = cliente._get(url)
    soup = BeautifulSoup(resposta.text, "html.parser")
    links: list[str] = []
    for ancora in soup.find_all("a", href=True):
        href = str(ancora["href"])
        if href in {"../", "./", "/"}:
            continue
        links.append(urljoin(resposta.url, href))
    return sorted(set(links))


def filtrar_links(
    links: Iterable[str],
    *,
    conter: Iterable[str] = (),
    terminar_com: Iterable[str] = (),
) -> list[str]:
    conter_norm = [x.casefold() for x in conter]
    finais_norm = [x.casefold() for x in terminar_com]
    resultado = []
    for link in links:
        nome = link.casefold()
        if conter_norm and not all(token in nome for token in conter_norm):
            continue
        if finais_norm and not any(nome.endswith(sufixo) for sufixo in finais_norm):
            continue
        resultado.append(link)
    return sorted(resultado)


def salvar_snapshot_indice(
    url: str,
    destino: Path,
    *,
    manifesto: Path | None = None,
    cliente: HttpClient | None = None,
) -> Path:
    cliente = cliente or HttpClient()
    links = listar_links_indice(url, cliente=cliente)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps({"url": url, "links": links}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if manifesto is not None:
        registrar_arquivo(manifesto, destino, origem=url)
    return destino
