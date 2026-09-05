from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

from .paths import resolve_paths
from .proveniencia import registrar_evento


ZIP_RE = re.compile(r"\.zip$", re.I)


def _links_snapshot(path: Path) -> list[str]:
    dados = json.loads(path.read_text(encoding="utf-8"))
    links = dados.get("links") if isinstance(dados, dict) else None
    if not isinstance(links, list):
        raise ValueError(f"Snapshot de indice invalido: {path}")
    return [str(x) for x in links if ZIP_RE.search(urlparse(str(x)).path)]


def _nome(url: str) -> str:
    return Path(urlparse(url).path).name


def _selecionar_por_tokens(links: list[str], *tokens: str) -> list[str]:
    termos = tuple(t.casefold() for t in tokens)
    return [u for u in links if all(t in _nome(u).casefold() for t in termos)]


def _classificar_entorno(links: list[str]) -> dict[str, list[str]]:
    """Classifica candidatos sem presumir nomes exatos dos arquivos publicados."""
    return {
        "domicilios": _selecionar_por_tokens(links, "domic"),
        "moradores": _selecionar_por_tokens(links, "morador"),
        "faces": _selecionar_por_tokens(links, "face"),
    }


def executar(raiz: Path) -> None:
    raiz = raiz.resolve()
    paths = resolve_paths(raiz)
    paths.create()
    manifesto = paths.manifests / "execucao.jsonl"

    snap_agreg = paths.raw / "ibge" / "indices_publicacao" / "censo2022_agregados_setor.json"
    snap_entorno = paths.raw / "ibge" / "indices_publicacao" / "censo2022_entorno_setor.json"
    for p in (snap_agreg, snap_entorno):
        if not p.exists():
            raise FileNotFoundError(f"Snapshot ausente: {p}. Execute primeiro --etapa 01.")

    agreg = _links_snapshot(snap_agreg)
    entorno = _links_snapshot(snap_entorno)

    # A/E/R dependem das variaveis domiciliares V00001, V00464, V00200, V00201,
    # V00312-V00316 e V00399-V00402. Nesta etapa nao se escolhe um arquivo pelo
    # nome presumido: registram-se os candidatos publicados para que a etapa 05b
    # possa validar cabecalhos/dicionarios antes do calculo.
    candidatos_domicilio = _selecionar_por_tokens(agreg, "domicilio")
    if not candidatos_domicilio:
        candidatos_domicilio = _selecionar_por_tokens(agreg, "domic")

    grupos_entorno = _classificar_entorno(entorno)
    unicos_entorno = {k: len(v) == 1 for k, v in grupos_entorno.items()}

    qa = {
        "status": "DIAGNOSTICO_ESTRUTURAL",
        "etapa": "05a",
        "objeto": "descoberta das fontes publicas necessarias ao ISAU-C3/C4",
        "formula_nuclear": "ISAU_C4=(A+E+R+D)/4; ISAU_C3=media dos dominios observados quando n>=3; PRIV=1-ISAU",
        "variaveis_aer_requeridas": [
            "V00001", "V00464", "V00200", "V00201",
            "V00312", "V00313", "V00314", "V00315", "V00316",
            "V00399", "V00400", "V00401", "V00402",
        ],
        "candidatos_agregados_domiciliares": candidatos_domicilio,
        "entorno": {
            "regra": "resolver tres universos independentes (domicilios, moradores e faces) e localizar semanticamente bueiro/boca de lobo antes do calculo D2",
            "candidatos_por_universo": grupos_entorno,
            "selecao_unica_por_universo": unicos_entorno,
        },
        "drenagem_D2": "D_exp=(D_dom+D_mor)/2; D_priv=0.5*D_exp+0.5*D_fac; D=1-D_priv/100",
        "politica_ausencias": "x/X, supressao e nao disponibilidade permanecem ausentes; nao imputar nem reconstruir por diferenca",
        "proximo_gate": "05b deve inspecionar cabecalhos/dicionarios dos candidatos e comprovar os codigos/denominadores antes de calcular A/E/R/D",
        "n_zips_agregados_publicados": len(agreg),
        "n_zips_entorno_publicados": len(entorno),
    }
    destino = paths.qa / "etapa05a_selecao_fontes_isau.json"
    destino.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    registrar_evento(manifesto, {"tipo": "etapa", "etapa": "05a", **qa, "saida": str(destino.relative_to(paths.data_root))})
    print(json.dumps(qa, ensure_ascii=False, indent=2))
