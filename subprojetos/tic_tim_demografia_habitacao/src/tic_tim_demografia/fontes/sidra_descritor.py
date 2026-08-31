from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


def _norm(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"\s+", " ", texto).strip().casefold()
    return texto


def _iter_dicts(obj: Any) -> Iterable[dict[str, Any]]:
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _iter_dicts(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iter_dicts(item)


def _primeiro(d: dict[str, Any], *chaves: str) -> Any:
    mapa = {_norm(k): v for k, v in d.items()}
    for chave in chaves:
        if _norm(chave) in mapa:
            return mapa[_norm(chave)]
    return None


@dataclass(frozen=True)
class Categoria:
    codigo: str
    nome: str


@dataclass(frozen=True)
class Classificacao:
    codigo: str
    nome: str
    categorias: tuple[Categoria, ...]


def carregar_descritor(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def extrair_classificacoes(descritor: Any) -> list[Classificacao]:
    """Extrai classificações SIDRA de maneira tolerante a variações de casing/estrutura.

    O descritor já mudou de forma entre tabelas e versões. Esta rotina não depende
    de uma posição fixa no JSON: procura objetos com código, nome e coleção de
    categorias. Se não houver evidência suficiente, não inventa códigos.
    """
    saida: list[Classificacao] = []
    vistos: set[tuple[str, str]] = set()

    for d in _iter_dicts(descritor):
        codigo = _primeiro(d, "Codigo", "Código", "Id", "ID")
        nome = _primeiro(d, "Nome", "Descricao", "Descrição", "Titulo", "Título")
        cats = _primeiro(d, "Categorias", "Categoria", "Valores", "Itens")
        if codigo is None or nome is None or not isinstance(cats, list):
            continue

        categorias: list[Categoria] = []
        for item in cats:
            if not isinstance(item, dict):
                continue
            cc = _primeiro(item, "Codigo", "Código", "Id", "ID", "Valor")
            cn = _primeiro(item, "Nome", "Descricao", "Descrição", "Titulo", "Título")
            if cc is None or cn is None:
                continue
            categorias.append(Categoria(str(cc), str(cn)))

        if not categorias:
            continue
        chave = (str(codigo), _norm(str(nome)))
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append(Classificacao(str(codigo), str(nome), tuple(categorias)))

    return saida


def localizar_classificacao(
    classificacoes: Iterable[Classificacao],
    *,
    termos_nome: Iterable[str],
) -> Classificacao:
    termos = tuple(_norm(t) for t in termos_nome)
    candidatas = [
        c for c in classificacoes if any(t in _norm(c.nome) for t in termos)
    ]
    if len(candidatas) != 1:
        nomes = [f"{c.codigo}:{c.nome}" for c in candidatas]
        raise ValueError(
            f"Classificação ambígua/ausente para termos {list(termos_nome)}; candidatas={nomes}"
        )
    return candidatas[0]


def localizar_categoria(
    classificacao: Classificacao,
    *,
    nomes_exatos: Iterable[str] = (),
    termos: Iterable[str] = (),
) -> Categoria:
    exatos = {_norm(x) for x in nomes_exatos}
    termos_n = tuple(_norm(x) for x in termos)

    candidatas = []
    for cat in classificacao.categorias:
        nome = _norm(cat.nome)
        if nome in exatos or any(t in nome for t in termos_n):
            candidatas.append(cat)

    if len(candidatas) != 1:
        nomes = [f"{c.codigo}:{c.nome}" for c in candidatas]
        raise ValueError(
            f"Categoria ambígua/ausente em {classificacao.nome}; candidatas={nomes}"
        )
    return candidatas[0]


def resumo_descritor(descritor: Any) -> dict[str, Any]:
    classificacoes = extrair_classificacoes(descritor)
    return {
        "n_classificacoes_detectadas": len(classificacoes),
        "classificacoes": [
            {
                "codigo": c.codigo,
                "nome": c.nome,
                "n_categorias": len(c.categorias),
                "categorias": [
                    {"codigo": x.codigo, "nome": x.nome} for x in c.categorias
                ],
            }
            for c in classificacoes
        ],
    }
