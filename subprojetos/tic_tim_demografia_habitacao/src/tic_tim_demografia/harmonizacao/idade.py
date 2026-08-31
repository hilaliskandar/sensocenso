from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


def _norm(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", texto).strip().casefold()


@dataclass(frozen=True)
class FaixaEtaria:
    rotulo: str
    minimo: int
    maximo: int | None


def interpretar_faixa_etaria(rotulo: str) -> FaixaEtaria | None:
    """Interpreta rótulos etários sem depender de códigos SIDRA.

    Retorna None para categorias como 'Total', 'Idade ignorada' ou rótulos
    incompatíveis com intervalos etários explícitos.
    """
    s = _norm(rotulo)
    if s in {"total", "idade ignorada", "ignorado", "sem declaracao"}:
        return None

    m = re.search(r"(\d+)\s*(?:a|ate|-)\s*(\d+)\s*anos?", s)
    if m:
        return FaixaEtaria(rotulo, int(m.group(1)), int(m.group(2)))

    m = re.search(r"(\d+)\s*anos?\s*(?:ou mais|e mais|e acima|ou acima)", s)
    if m:
        return FaixaEtaria(rotulo, int(m.group(1)), None)

    m = re.fullmatch(r"(\d+)\s*anos?", s)
    if m:
        idade = int(m.group(1))
        return FaixaEtaria(rotulo, idade, idade)

    m = re.search(r"menos de\s*(\d+)\s*anos?", s)
    if m:
        limite = int(m.group(1))
        return FaixaEtaria(rotulo, 0, limite - 1)

    return None


def banda_harmonizada(faixa: FaixaEtaria) -> str | None:
    """Classifica apenas intervalos inteiramente contidos nas bandas canônicas.

    Faixas que cruzem 14/15 ou 59/60 retornam None para impedir alocação
    arbitrária. Esse comportamento materializa a regra de não interpolação.
    """
    maximo = faixa.maximo
    if maximo is not None and 0 <= faixa.minimo and maximo <= 14:
        return "0_14"
    if maximo is not None and 15 <= faixa.minimo and maximo <= 59:
        return "15_59"
    if faixa.minimo >= 60:
        return "60_mais"
    return None


def mapear_rotulos_para_bandas(rotulos: list[str]) -> dict[str, str]:
    saida: dict[str, str] = {}
    for rotulo in rotulos:
        faixa = interpretar_faixa_etaria(rotulo)
        if faixa is None:
            continue
        banda = banda_harmonizada(faixa)
        if banda is not None:
            saida[rotulo] = banda
    return saida
