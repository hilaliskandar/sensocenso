from __future__ import annotations

from pathlib import Path

from .config import carregar_fontes
from .fontes.sidra import baixar_descritor_tabela
from .proveniencia import registrar_evento


def executar(raiz: Path) -> None:
    raiz = raiz.resolve()
    fontes = carregar_fontes(raiz / "config/fontes.yml")
    manifesto = raiz / "manifestos/execucao.jsonl"

    saidas: list[str] = []
    for chave in ("sidra_2000_idade", "sidra_2010_idade"):
        tabela = int(fontes["fontes"][chave]["tabela"])
        destino = raiz / f"data/raw/sidra/descritor_tabela_{tabela}.json"
        baixar_descritor_tabela(tabela, destino, manifesto=manifesto)
        saidas.append(str(destino.relative_to(raiz)))

    registrar_evento(
        manifesto,
        {
            "tipo": "etapa",
            "etapa": "01a",
            "status": "OK",
            "descricao": "descritores SIDRA baixados e congelados",
            "saidas": saidas,
        },
    )
    print("Descritores SIDRA congelados:")
    for saida in saidas:
        print(f"- {saida}")
