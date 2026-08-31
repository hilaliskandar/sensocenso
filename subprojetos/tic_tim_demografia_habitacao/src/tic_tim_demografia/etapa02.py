from __future__ import annotations

import json
from pathlib import Path

from .config import carregar_fontes
from .fontes.sidra_descritor import (
    carregar_descritor,
    extrair_classificacoes,
    localizar_categoria,
    localizar_classificacao,
)
from .harmonizacao.idade import selecionar_particao_quinquenal
from .paths import resolve_paths
from .proveniencia import registrar_evento


TERMOS_IDADE = ("grupos de idade", "grupo de idade", "idade")
TERMOS_SEXO = ("sexo",)
TERMOS_SITUACAO = ("situacao do domicilio", "situação do domicílio")


def _resolver_tabela(descritor_path: Path, tabela: int, periodo: int) -> dict:
    descritor = carregar_descritor(descritor_path)
    classificacoes = extrair_classificacoes(descritor)

    idade = localizar_classificacao(classificacoes, termos_nome=TERMOS_IDADE)
    sexo = localizar_classificacao(classificacoes, termos_nome=TERMOS_SEXO)
    sexo_total = localizar_categoria(sexo, nomes_exatos=("Total",))

    situacao = None
    situacao_total = None
    try:
        situacao = localizar_classificacao(classificacoes, termos_nome=TERMOS_SITUACAO)
        situacao_total = localizar_categoria(situacao, nomes_exatos=("Total",))
    except ValueError:
        pass

    # Os descritores oferecem simultaneamente classes agregadas e idades simples.
    # A série histórica auditada usa 21 classes mutuamente exclusivas: quinquênios
    # 0–4 ... 95–99 e 100+. Selecionar todas as categorias que cabem em uma banda
    # causaria dupla contagem; por isso a partição é validada antes da consulta.
    mapa_idade = selecionar_particao_quinquenal([c.nome for c in idade.categorias])
    codigos_por_banda = {"0_14": [], "15_59": [], "60_mais": []}
    ignoradas = []
    for cat in idade.categorias:
        banda = mapa_idade.get(cat.nome)
        if banda is None:
            ignoradas.append({"codigo": cat.codigo, "nome": cat.nome})
        else:
            codigos_por_banda[banda].append({"codigo": cat.codigo, "nome": cat.nome})

    faltantes = [b for b, itens in codigos_por_banda.items() if not itens]
    if faltantes:
        raise ValueError(
            f"Tabela {tabela}: bandas harmonizadas sem categorias detectadas: {faltantes}"
        )
    n_classes = sum(len(v) for v in codigos_por_banda.values())
    if n_classes != 21:
        raise AssertionError(f"Tabela {tabela}: esperadas 21 classes etárias não sobrepostas; obtidas={n_classes}")

    return {
        "tabela": tabela,
        "periodo": periodo,
        "classificacao_idade": {"codigo": idade.codigo, "nome": idade.nome},
        "classificacao_sexo": {"codigo": sexo.codigo, "nome": sexo.nome},
        "sexo_total": {"codigo": sexo_total.codigo, "nome": sexo_total.nome},
        "classificacao_situacao": None
        if situacao is None
        else {"codigo": situacao.codigo, "nome": situacao.nome},
        "situacao_total": None
        if situacao_total is None
        else {"codigo": situacao_total.codigo, "nome": situacao_total.nome},
        "categorias_idade_por_banda": codigos_por_banda,
        "categorias_idade_nao_utilizadas": ignoradas,
        "n_classes_idade_selecionadas": n_classes,
        "regra": (
            "usar partição não sobreposta de 21 classes: quinquênios 0–4 a 95–99 e 100+; "
            "agregar em 0–14, 15–59 e 60+; não interpolar"
        ),
    }


def executar(raiz: Path) -> None:
    raiz = raiz.resolve()
    fontes = carregar_fontes(raiz / "config/fontes.yml")
    paths = resolve_paths(raiz)
    paths.create()

    resolvidas = []
    for chave in ("sidra_2000_idade", "sidra_2010_idade"):
        fonte = fontes["fontes"][chave]
        tabela = int(fonte["tabela"])
        periodo = int(fonte["periodo"])
        descritor = paths.raw / "ibge" / "sidra" / "descritores" / f"descritor_tabela_{tabela}.json"
        if not descritor.exists():
            raise FileNotFoundError(
                f"Descritor SIDRA ausente: {descritor}. Execute primeiro --etapa 01."
            )
        resolvidas.append(_resolver_tabela(descritor, tabela, periodo))

    destino = paths.qa / "sidra_selecao_harmonizacao_2000_2010.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(resolvidas, ensure_ascii=False, indent=2), encoding="utf-8")

    registrar_evento(
        paths.manifests / "execucao.jsonl",
        {
            "tipo": "etapa",
            "etapa": "02a",
            "status": "OK",
            "descricao": (
                "classificações SIDRA resolvidas por rótulo; partição etária de 21 classes "
                "mutuamente exclusivas validada antes da harmonização"
            ),
            "saida": str(destino.relative_to(paths.data_root)),
        },
    )
    print(f"Seleção SIDRA resolvida: {destino}")
