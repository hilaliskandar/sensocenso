from __future__ import annotations

import json
from pathlib import Path

from .config import carregar_fontes, carregar_municipios, carregar_parametros
from .paths import ENV_DATA_ROOT, resolve_paths
from .proveniencia import registrar_evento


def executar(raiz: Path) -> None:
    raiz = raiz.resolve()
    config_dir = raiz / "config"
    municipios = carregar_municipios(config_dir / "municipios.yml")
    parametros = carregar_parametros(config_dir / "parametros.yml")
    fontes = carregar_fontes(config_dir / "fontes.yml")
    paths = resolve_paths(raiz)
    paths.create()

    resumo = {
        "municipios": len(municipios),
        "coroa_interna": sum(m.coroa == "interna" for m in municipios),
        "coroa_externa": sum(m.coroa == "externa" for m in municipios),
        "anos_censitarios": parametros["projeto"]["anos_censitarios"],
        "fontes_declaradas": sorted(fontes["fontes"].keys()),
        "data_root": str(paths.data_root),
        "data_root_externalizado": ENV_DATA_ROOT in __import__("os").environ,
    }

    saida = paths.qa / "etapa00_configuracao.json"
    saida.write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    registrar_evento(
        paths.manifests / "execucao.jsonl",
        {"tipo": "etapa", "etapa": "00", "status": "OK", **resumo},
    )
    print(json.dumps(resumo, ensure_ascii=False, indent=2))
