from __future__ import annotations

from pathlib import Path

from .config import carregar_fontes
from .fontes.sidra import baixar_descritor_tabela
from .paths import resolve_paths
from .proveniencia import registrar_evento


def executar(raiz: Path) -> None:
    raiz = raiz.resolve()
    fontes = carregar_fontes(raiz / "config/fontes.yml")
    paths = resolve_paths(raiz)
    paths.create()
    manifesto = paths.manifests / "execucao.jsonl"

    saidas: list[str] = []
    destino_sidra = paths.raw / "ibge" / "sidra" / "descritores"
    destino_sidra.mkdir(parents=True, exist_ok=True)

    for chave in ("sidra_2000_idade", "sidra_2010_idade"):
        tabela = int(fontes["fontes"][chave]["tabela"])
        destino = destino_sidra / f"descritor_tabela_{tabela}.json"
        baixar_descritor_tabela(tabela, destino, manifesto=manifesto)
        saidas.append(str(destino.relative_to(paths.data_root)))

    registrar_evento(
        manifesto,
        {
            "tipo": "etapa",
            "etapa": "01a",
            "status": "OK",
            "descricao": "descritores SIDRA baixados e congelados",
            "saidas_relativas_data_root": saidas,
        },
    )
    print("Descritores SIDRA congelados:")
    for saida in saidas:
        print(f"- {saida}")
