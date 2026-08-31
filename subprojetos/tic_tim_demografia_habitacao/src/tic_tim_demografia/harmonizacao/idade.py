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
    """Interpreta rótulos etários sem depender de códigos SIDRA."""
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
    """Classifica apenas intervalos inteiramente contidos nas bandas canônicas."""
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


def selecionar_particao_quinquenal(rotulos: list[str]) -> dict[str, str]:
    """Seleciona a partição etária não sobreposta usada na série histórica.

    Os descritores SIDRA 1518 e 3107 oferecem simultaneamente faixas agregadas
    (por exemplo, ``0 a 4 anos``), idades simples e alguns agregados abertos.
    Somar todas as categorias contidas em 0–14/15–59/60+ produz dupla contagem.

    A série auditada foi construída com 21 classes mutuamente exclusivas:
    quinquênios 0–4, 5–9, ..., 95–99 e a classe aberta 100+. Esta função
    identifica essa partição pelos rótulos, sem depender dos códigos SIDRA, e
    valida cobertura contínua e ausência de sobreposição antes de retornar o
    mapeamento para as três bandas analíticas.
    """
    selecionadas: list[FaixaEtaria] = []
    for rotulo in rotulos:
        faixa = interpretar_faixa_etaria(rotulo)
        if faixa is None:
            continue
        if faixa.maximo is not None:
            if faixa.minimo % 5 == 0 and faixa.maximo == faixa.minimo + 4 and faixa.minimo <= 95:
                selecionadas.append(faixa)
        elif faixa.minimo == 100:
            selecionadas.append(faixa)

    selecionadas.sort(key=lambda f: f.minimo)
    esperados = [(inicio, inicio + 4) for inicio in range(0, 100, 5)] + [(100, None)]
    observados = [(f.minimo, f.maximo) for f in selecionadas]
    if observados != esperados:
        raise ValueError(
            "Descritor SIDRA não contém a partição etária quinquenal completa e não sobreposta "
            f"esperada; observados={observados}"
        )

    mapa: dict[str, str] = {}
    for faixa in selecionadas:
        banda = banda_harmonizada(faixa)
        if banda is None:
            raise AssertionError(f"Faixa canônica não alocável: {faixa}")
        mapa[faixa.rotulo] = banda
    if len(mapa) != 21:
        raise AssertionError(f"Partição histórica deve ter 21 classes; obtidas={len(mapa)}")
    return mapa
