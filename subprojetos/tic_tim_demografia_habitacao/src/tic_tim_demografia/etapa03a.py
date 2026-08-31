from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

from .config import carregar_fontes
from .fontes.sidra_descritor import (
    Classificacao,
    carregar_descritor,
    extrair_classificacoes,
    localizar_categoria,
    localizar_classificacao,
)
from .paths import resolve_paths
from .proveniencia import registrar_evento


PADRAO_BASICO = re.compile(r"^Agregados_por_setores_basico_BR(?:_\d{8})?\.zip$", re.I)
PADRAO_DOMICILIO1 = re.compile(
    r"^Agregados_por_setores_caracteristicas_domicilio1_BR(?:_\d{8})?\.zip$", re.I
)
TERMOS_SITUACAO = ("situacao do domicilio", "situação do domicílio")
TERMOS_NUMERO_MORADORES = ("numero de moradores", "número de moradores")


def _norm(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", texto).strip().casefold()


def _carregar_links_snapshot(path: Path) -> list[str]:
    dados = json.loads(path.read_text(encoding="utf-8"))
    links = dados.get("links") if isinstance(dados, dict) else None
    if not isinstance(links, list):
        raise ValueError(f"Snapshot de índice inválido: {path}")
    return [str(x) for x in links]


def _selecionar_unico(links: list[str], padrao: re.Pattern[str], descricao: str) -> str:
    candidatos = [
        link for link in links if padrao.match(Path(urlparse(link).path).name)
    ]
    if len(candidatos) != 1:
        raise ValueError(f"Seleção ambígua/ausente para {descricao}: {candidatos}")
    return candidatos[0]


def _localizar_numero_moradores(classificacoes: list[Classificacao]) -> Classificacao:
    """Resolve a dimensão de número de moradores sem depender de um código fixo.

    A tabela 185 pode variar na redação do rótulo. Primeiro tenta o nome semântico;
    se não houver correspondência única, usa a estrutura das categorias: várias
    classes iniciadas por números, incluindo explicitamente 1 e 2 moradores.
    """
    try:
        return localizar_classificacao(
            classificacoes, termos_nome=TERMOS_NUMERO_MORADORES
        )
    except ValueError:
        candidatas: list[Classificacao] = []
        for classificacao in classificacoes:
            nomes = [_norm(c.nome) for c in classificacao.categorias]
            numericas = [n for n in nomes if re.match(r"^\d+", n)]
            tem_1 = any(re.match(r"^1\b", n) for n in nomes)
            tem_2 = any(re.match(r"^2\b", n) for n in nomes)
            evidencia_pessoas = sum(
                ("morador" in n) or ("pessoa" in n) for n in numericas
            )
            if len(numericas) >= 5 and tem_1 and tem_2 and evidencia_pessoas >= 2:
                candidatas.append(classificacao)
        if len(candidatas) != 1:
            nomes = [f"{c.codigo}:{c.nome}" for c in candidatas]
            raise ValueError(
                "Dimensão de número de moradores ambígua/ausente; "
                f"candidatas estruturais={nomes}"
            )
        return candidatas[0]


def _resolver_tabela_156(descritor_path: Path) -> dict:
    classificacoes = extrair_classificacoes(carregar_descritor(descritor_path))
    situacao = localizar_classificacao(classificacoes, termos_nome=TERMOS_SITUACAO)
    total = localizar_categoria(situacao, nomes_exatos=("Total",))
    return {
        "tabela": 156,
        "papel": (
            "domicílios particulares ocupados/permanentes, moradores no universo "
            "compatível e tamanho médio, conforme variáveis efetivamente expostas pela tabela"
        ),
        "classificacao_situacao": {"codigo": situacao.codigo, "nome": situacao.nome},
        "situacao_total": {"codigo": total.codigo, "nome": total.nome},
        "regra": (
            "não fixar código de variável nesta etapa; a etapa 03b deverá resolver e "
            "validar as variáveis retornadas antes de calcular DPO ou tamanho médio"
        ),
    }


def _resolver_tabela_185(descritor_path: Path) -> dict:
    classificacoes = extrair_classificacoes(carregar_descritor(descritor_path))
    situacao = localizar_classificacao(classificacoes, termos_nome=TERMOS_SITUACAO)
    total = localizar_categoria(situacao, nomes_exatos=("Total",))
    moradores = _localizar_numero_moradores(classificacoes)

    um = localizar_categoria(
        moradores,
        nomes_exatos=("1 morador", "1 pessoa"),
        termos=("1 morador", "1 pessoa"),
    )
    return {
        "tabela": 185,
        "papel": "distribuição dos domicílios por número de moradores e identificação de unipessoais",
        "classificacao_situacao": {"codigo": situacao.codigo, "nome": situacao.nome},
        "situacao_total": {"codigo": total.codigo, "nome": total.nome},
        "classificacao_numero_moradores": {
            "codigo": moradores.codigo,
            "nome": moradores.nome,
            "n_categorias": len(moradores.categorias),
        },
        "categoria_um_morador": {"codigo": um.codigo, "nome": um.nome},
        "categorias": [
            {"codigo": c.codigo, "nome": c.nome} for c in moradores.categorias
        ],
        "regra": (
            "unipessoal é a categoria de um morador; o denominador deve ser o universo "
            "compatível e validado, sem converter supressões em zero"
        ),
    }


def executar(raiz: Path) -> None:
    raiz = raiz.resolve()
    fontes = carregar_fontes(raiz / "config/fontes.yml")
    paths = resolve_paths(raiz)
    paths.create()

    resolvidas = []
    for chave, resolver in (
        ("sidra_2000_2010_domicilios", _resolver_tabela_156),
        ("sidra_2000_2010_unipessoais", _resolver_tabela_185),
    ):
        tabela = int(fontes["fontes"][chave]["tabela"])
        descritor = (
            paths.raw
            / "ibge"
            / "sidra"
            / "descritores"
            / f"descritor_tabela_{tabela}.json"
        )
        if not descritor.exists():
            raise FileNotFoundError(
                f"Descritor SIDRA ausente: {descritor}. Execute primeiro --etapa 01."
            )
        resolvidas.append(resolver(descritor))

    snapshot = (
        paths.raw
        / "ibge"
        / "indices_publicacao"
        / "censo2022_agregados_setor.json"
    )
    if not snapshot.exists():
        raise FileNotFoundError(
            f"Snapshot Censo 2022 ausente: {snapshot}. Execute primeiro --etapa 01."
        )
    links = _carregar_links_snapshot(snapshot)
    url_basico = _selecionar_unico(links, PADRAO_BASICO, "Básico 2022")
    url_domicilio1 = _selecionar_unico(
        links, PADRAO_DOMICILIO1, "Características do domicílio 1 — 2022"
    )

    resultado = {
        "status": "OK",
        "etapa": "03a",
        "fontes_historicas": resolvidas,
        "fontes_2022": {
            "basico": {
                "url": url_basico,
                "uso_previsto": "DPO e recortes municipal/urbano/rural quando aplicável",
            },
            "caracteristicas_domicilio1": {
                "url": url_domicilio1,
                "uso_previsto": (
                    "distribuição por número de moradores e demais campos somente após "
                    "resolução explícita do dicionário de variáveis"
                ),
            },
        },
        "bloqueios_para_03b": [
            "resolver as variáveis/medidas da tabela 156 sem presumir código",
            "resolver o denominador histórico da participação de unipessoais na tabela 185",
            "resolver no dicionário 2022 V00017–V00026 e seu universo compatível",
            "confirmar a fonte exata do tamanho médio domiciliar 2022 antes de reproduzi-lo",
        ],
        "principio": (
            "produtos históricos auditados servem como oráculo de regressão; não são fonte "
            "de cálculo do novo pipeline"
        ),
    }

    destino = paths.qa / "etapa03a_selecao_fontes_domicilios.json"
    destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    registrar_evento(
        paths.manifests / "execucao.jsonl",
        {
            "tipo": "etapa",
            "etapa": "03a",
            "status": "OK",
            "descricao": "fontes e dimensões de domicílios resolvidas sem iniciar cálculos ambíguos",
            "saida": str(destino.relative_to(paths.data_root)),
        },
    )
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
