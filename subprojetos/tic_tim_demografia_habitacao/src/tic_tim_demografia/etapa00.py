from __future__ import annotations

import json
from pathlib import Path

from .config import carregar_fontes, carregar_municipios, carregar_parametros
from .proveniencia import registrar_evento


DIRETORIOS = [
    "data/raw",
    "data/interim",
    "data/processed",
    "outputs/tabelas",
    "outputs/mapas",
    "outputs/geodata",
    "outputs/qa",
    "manifestos",
]


def executar(raiz: Path) -> None:
    raiz = raiz.resolve()
    config_dir = raiz / "config"
    municipios = carregar_municipios(config_dir / "municipios.yml")
    parametros = carregar_parametros(config_dir / "parametros.yml")
    fontes = carregar_fontes(config_dir / "fontes.yml")

    for rel in DIRETORIOS:
        (raiz / rel).mkdir(parents=True, exist_ok=True)

    resumo = {
        "municipios": len(municipios),
        "coroa_interna": sum(m.coroa == "interna" for m in municipios),
        "coroa_externa": sum(m.coroa == "externa" for m in municipios),
        "anos_censitarios": parametros["projeto"]["anos_censitarios"],
        "fontes_declaradas": sorted(fontes["fontes"].keys()),
    }

    saida = raiz / "outputs/qa/etapa00_configuracao.json"
    saida.write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    registrar_evento(
        raiz / "manifestos/execucao.jsonl",
        {"tipo": "etapa", "etapa": "00", "status": "OK", **resumo},
    )
    print(json.dumps(resumo, ensure_ascii=False, indent=2))
