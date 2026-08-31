from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from openpyxl import load_workbook

from .paths import resolve_paths
from .proveniencia import registrar_arquivo, registrar_evento


VAR_ENTORNO_RE = re.compile(r"\bV0(?:50|52|54)\d{2}\b", re.I)
UNIVERSO_POR_PREFIXO = {"V050": "domicilios", "V052": "moradores", "V054": "faces"}

ATRIBUTOS = {
    "bueiro_boca_de_lobo": ("bueiro", "boca de lobo", "boca-de-lobo"),
    "calcada": ("calcada",),
    "pavimentacao": ("pavimentacao", "pavimentada", "pavimentado"),
    "iluminacao_publica": ("iluminacao publica", "iluminacao"),
    "arborizacao": ("arborizacao", "arborizada", "arborizado"),
    "rampa_cadeirante": ("rampa para cadeirante", "rampa"),
    "obstaculo_calcada": ("obstaculo na calcada", "obstaculos na calcada", "obstaculo"),
    "ponto_onibus": ("ponto de onibus", "parada de onibus"),
    "infraestrutura_cicloviaria": (
        "via sinalizada para bicicleta",
        "via sinalizada para bicicletas",
        "bicicleta",
        "ciclovia",
        "ciclofaixa",
    ),
}


def _normalizar(valor: object) -> str:
    texto = " ".join(str(valor or "").replace("\n", " ").split()).strip()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c)).casefold()


def _texto_original(valores: list[object]) -> str:
    return " | ".join(" ".join(str(v or "").replace("\n", " ").split()).strip() for v in valores if v not in (None, ""))


def _categoria(texto_norm: str) -> str | None:
    if "nao declarado" in texto_norm or "nao-declarado" in texto_norm:
        return "nao_declarado"
    if re.search(r"(?:^|\W)nao(?:\W|$)", texto_norm) or "sem " in texto_norm:
        return "nao"
    if re.search(r"(?:^|\W)sim(?:\W|$)", texto_norm) or "com " in texto_norm:
        return "sim"
    return None


def inspecionar_dicionario(path: Path) -> dict:
    wb = load_workbook(path, read_only=True, data_only=True)
    achados: dict[str, list[dict]] = {k: [] for k in ATRIBUTOS}
    for ws in wb.worksheets:
        linhas = [list(row) for row in ws.iter_rows(values_only=True)]
        for i, valores in enumerate(linhas):
            original = _texto_original(valores)
            norm = _normalizar(original)
            atributos = [
                nome
                for nome, termos in ATRIBUTOS.items()
                if any(_normalizar(termo) in norm for termo in termos)
            ]
            if not atributos:
                continue

            contexto_linhas = linhas[max(0, i - 1) : min(len(linhas), i + 2)]
            contexto = " || ".join(_texto_original(v) for v in contexto_linhas)
            codigos = sorted(set(VAR_ENTORNO_RE.findall(original.upper())))
            if not codigos:
                codigos = sorted(set(VAR_ENTORNO_RE.findall(contexto.upper())))
            categoria = _categoria(norm)
            for atributo in atributos:
                achados[atributo].append(
                    {
                        "planilha": ws.title,
                        "linha": i + 1,
                        "texto": original,
                        "contexto": contexto if contexto != original else None,
                        "categoria": categoria,
                        "codigos": codigos,
                    }
                )
    wb.close()
    return achados


def resumir_codigos(achados: dict[str, list[dict]]) -> dict:
    resumo: dict[str, dict] = {}
    for atributo, linhas in achados.items():
        por_universo = {
            u: {"sim": set(), "nao": set(), "nao_declarado": set(), "sem_categoria": set()}
            for u in UNIVERSO_POR_PREFIXO.values()
        }
        for item in linhas:
            categoria = item.get("categoria") or "sem_categoria"
            for codigo in item.get("codigos", []):
                codigo = str(codigo).upper()
                universo = UNIVERSO_POR_PREFIXO.get(codigo[:4])
                if universo:
                    por_universo[universo][categoria].add(codigo)
        resumo[atributo] = {
            universo: {cat: sorted(vals) for cat, vals in cats.items()}
            for universo, cats in por_universo.items()
        }
    return resumo


def executar(raiz: Path) -> None:
    raiz = raiz.resolve()
    paths = resolve_paths(raiz)
    paths.create()
    manifesto = paths.manifests / "execucao.jsonl"

    qa05b_path = paths.qa / "etapa05b_inspecao_fontes_isau.json"
    if not qa05b_path.exists():
        raise FileNotFoundError(f"Pré-requisito 06a ausente: {qa05b_path}")
    qa05b = json.loads(qa05b_path.read_text(encoding="utf-8"))
    nome_resolvedor = qa05b.get("dicionario_resolvedor_bueiro")
    if not nome_resolvedor:
        raise ValueError("05b não registrou dicionário oficial resolvedor de bueiro.")

    raw_doc = paths.raw / "ibge" / "censo2022" / "isau" / "documentacao"
    candidatos = sorted(raw_doc.glob("*.xlsx"))
    if not candidatos:
        raise FileNotFoundError(
            "Nenhum dicionário XLSX materializado por 05b. A etapa 06a não presume nome ou códigos."
        )

    resultados = []
    for arquivo in candidatos:
        try:
            achados = inspecionar_dicionario(arquivo)
            n_total = sum(len(v) for v in achados.values())
            if n_total:
                resultados.append(
                    {
                        "arquivo": arquivo.name,
                        "n_achados": n_total,
                        "achados": achados,
                        "resumo_codigos": resumir_codigos(achados),
                    }
                )
        except Exception as exc:
            resultados.append(
                {"arquivo": arquivo.name, "erro": f"{type(exc).__name__}: {exc}"}
            )

    if not resultados:
        raise ValueError("Nenhuma evidência semântica de atributos de entorno encontrada no dicionário oficial.")

    qa = {
        "status": "DIAGNOSTICO_SEMANTICO",
        "etapa": "06a",
        "objetivo": (
            "descobrir no dicionário oficial os códigos dos atributos de entorno antes de qualquer cálculo"
        ),
        "atributos_nucleares_f3": [
            "bueiro_boca_de_lobo",
            "calcada",
            "pavimentacao",
            "iluminacao_publica",
            "arborizacao",
        ],
        "atributos_complementares": [
            "rampa_cadeirante",
            "obstaculo_calcada",
            "ponto_onibus",
            "infraestrutura_cicloviaria",
        ],
        "dicionario_resolvedor_05b": nome_resolvedor,
        "resultados": resultados,
        "regra": (
            "06b só poderá calcular percentuais de ausência depois de cada código Sim/Não/Não declarado ser "
            "semanticamente resolvido e confirmado nos cabeçalhos oficiais dos universos correspondentes."
        ),
        "regra_f3": (
            "F3 usa cinco atributos principais desagregados; sinaliza setor com pelo menos dois componentes "
            "no quartil superior de ausência. Se Q75=0, exige valor estritamente positivo."
        ),
    }
    destino = paths.qa / "etapa06a_gate_semantico_entorno.json"
    destino.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    registrar_arquivo(manifesto, destino, origem="Gate semântico 06a - entorno urbano")
    registrar_evento(manifesto, {"tipo": "etapa", "etapa": "06a", "status": qa["status"]})
    print(json.dumps(qa, ensure_ascii=False, indent=2))
