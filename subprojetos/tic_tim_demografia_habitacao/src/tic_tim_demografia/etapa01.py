from __future__ import annotations

import json
from pathlib import Path

from .config import carregar_fontes
from .fontes.http import salvar_snapshot_indice
from .fontes.sidra import baixar_descritor_tabela
from .fontes.sidra_descritor import carregar_descritor, resumo_descritor
from .paths import resolve_paths
from .proveniencia import registrar_evento


FONTES_SIDRA_COM_DESCRITOR = (
    "sidra_2000_idade",
    "sidra_2010_idade",
    "sidra_2000_2010_domicilios",
    "sidra_2000_2010_unipessoais",
)

FONTES_COM_INDICE = (
    "censo2022_agregados_setor",
    "censo2022_entorno_setor",
    "censo2022_fcu",
    "censo2022_cnefe_municipios",
)


def executar(raiz: Path) -> None:
    raiz = raiz.resolve()
    fontes = carregar_fontes(raiz / "config/fontes.yml")
    paths = resolve_paths(raiz)
    paths.create()
    manifesto = paths.manifests / "execucao.jsonl"

    saidas: list[str] = []

    # 01a — congela todos os descritores SIDRA usados pelo pipeline antes de
    # resolver classificações, variáveis ou construir consultas.
    destino_sidra = paths.raw / "ibge" / "sidra" / "descritores"
    destino_sidra.mkdir(parents=True, exist_ok=True)
    destino_qa_sidra = paths.qa / "sidra_descritores"
    destino_qa_sidra.mkdir(parents=True, exist_ok=True)

    tabelas_vistas: set[int] = set()
    for chave in FONTES_SIDRA_COM_DESCRITOR:
        tabela = int(fontes["fontes"][chave]["tabela"])
        if tabela in tabelas_vistas:
            continue
        tabelas_vistas.add(tabela)
        destino = destino_sidra / f"descritor_tabela_{tabela}.json"
        if not destino.exists():
            baixar_descritor_tabela(tabela, destino, manifesto=manifesto)
        saidas.append(str(destino.relative_to(paths.data_root)))

        resumo = resumo_descritor(carregar_descritor(destino))
        resumo_path = destino_qa_sidra / f"descritor_tabela_{tabela}_resumo.json"
        resumo_path.write_text(
            json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        saidas.append(str(resumo_path.relative_to(paths.data_root)))

    # 01b — congela os índices públicos do IBGE. O snapshot permite saber quais
    # arquivos estavam publicados no momento da execução, sem depender de Drive
    # ou de uma seleção manual feita em navegador.
    destino_indices = paths.raw / "ibge" / "indices_publicacao"
    destino_indices.mkdir(parents=True, exist_ok=True)
    for chave in FONTES_COM_INDICE:
        fonte = fontes["fontes"][chave]
        url = str(fonte["discovery_url"])
        destino = destino_indices / f"{chave}.json"
        if not destino.exists():
            salvar_snapshot_indice(url, destino, manifesto=manifesto)
        saidas.append(str(destino.relative_to(paths.data_root)))

    registrar_evento(
        manifesto,
        {
            "tipo": "etapa",
            "etapa": "01",
            "status": "OK",
            "descricao": (
                "descritores SIDRA, resumos estruturais e snapshots dos índices "
                "públicos IBGE congelados"
            ),
            "saidas_relativas_data_root": saidas,
        },
    )
    print("Fontes de descoberta congeladas:")
    for saida in saidas:
        print(f"- {saida}")
