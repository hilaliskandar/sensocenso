from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path
from urllib.parse import urlparse

from .fontes.http import HttpClient
from .paths import resolve_paths
from .proveniencia import registrar_evento


VARIAVEIS_AER = [
    "V00001", "V00464", "V00200", "V00201",
    "V00312", "V00313", "V00314", "V00315", "V00316",
    "V00399", "V00400", "V00401", "V00402",
]


def _carregar_json(path: Path) -> dict:
    dados = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(dados, dict):
        raise ValueError(f"JSON estrutural invalido: {path}")
    return dados


def _nome(url: str) -> str:
    return Path(urlparse(url).path).name


def _selecionar_domicilios(candidatos: list[str]) -> list[str]:
    """Mantem somente os tres arquivos gerais de caracteristicas domiciliares."""
    escolhidos = []
    for url in candidatos:
        nome = _nome(url).casefold()
        if any(f"caracteristicas_domicilio{i}" in nome for i in (1, 2, 3)):
            escolhidos.append(url)
    if len(escolhidos) != 3:
        raise ValueError(f"Esperados tres arquivos gerais de domicilio; encontrados={escolhidos}")
    return sorted(escolhidos)


def _detectar_encoding(bruto: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252", "latin1"):
        try:
            bruto.decode(enc, errors="strict")
            return enc
        except UnicodeDecodeError:
            continue
    raise ValueError("Codificacao nao reconhecida no cabecalho CSV.")


def _cabecalho_csv(bruto: bytes) -> tuple[str, str, list[str]]:
    enc = _detectar_encoding(bruto)
    texto = bruto.decode(enc, errors="strict")
    primeira = texto.splitlines()[0] if texto.splitlines() else ""
    contagens = {";": primeira.count(";"), ",": primeira.count(","), "\t": primeira.count("\t")}
    sep, n = max(contagens.items(), key=lambda item: item[1])
    if n == 0:
        raise ValueError("Separador CSV nao reconhecido.")
    colunas = next(csv.reader(io.StringIO(primeira), delimiter=sep))
    return enc, sep, [str(c).strip() for c in colunas]


def inspecionar_zip(path: Path) -> dict:
    """Le apenas membros e a primeira linha dos CSVs, sem carregar a base integral."""
    csvs = []
    with zipfile.ZipFile(path) as zf:
        membros = zf.namelist()
        for membro in membros:
            if not membro.casefold().endswith(".csv"):
                continue
            with zf.open(membro) as f:
                bruto = f.readline()
            enc, sep, colunas = _cabecalho_csv(bruto)
            csvs.append(
                {
                    "membro": membro,
                    "encoding": enc,
                    "separador": sep,
                    "n_colunas": len(colunas),
                    "colunas": colunas,
                }
            )
    if not csvs:
        raise ValueError(f"ZIP sem CSV: {path}")
    return {"arquivo": path.name, "membros": membros, "csvs": csvs}


def _baixar_se_ausente(cliente: HttpClient, url: str, destino: Path, manifesto: Path) -> Path:
    if destino.exists():
        return destino
    return cliente.baixar_arquivo(url, destino, manifesto=manifesto)


def _mapear_variaveis(inspecoes: list[dict], variaveis: list[str]) -> dict[str, list[str]]:
    mapa = {v: [] for v in variaveis}
    for item in inspecoes:
        for csv_info in item["csvs"]:
            colunas = set(csv_info["colunas"])
            for var in variaveis:
                if var in colunas:
                    mapa[var].append(f"{item['arquivo']}::{csv_info['membro']}")
    return mapa


def executar(raiz: Path) -> None:
    raiz = raiz.resolve()
    paths = resolve_paths(raiz)
    paths.create()
    manifesto = paths.manifests / "execucao.jsonl"

    qa05a_path = paths.qa / "etapa05a_selecao_fontes_isau.json"
    if not qa05a_path.exists():
        raise FileNotFoundError(f"Gate 05a ausente: {qa05a_path}. Execute primeiro --etapa 05a.")
    qa05a = _carregar_json(qa05a_path)

    urls_dom = _selecionar_domicilios(list(qa05a["candidatos_agregados_domiciliares"]))
    entorno = qa05a["entorno"]["candidatos_por_universo"]
    urls_entorno: dict[str, str] = {}
    for universo in ("domicilios", "moradores", "faces"):
        candidatos = list(entorno.get(universo, []))
        if len(candidatos) != 1:
            raise ValueError(f"Entorno {universo}: selecao nao unica: {candidatos}")
        urls_entorno[universo] = candidatos[0]

    cliente = HttpClient(timeout=600)
    raw_dom = paths.raw / "ibge" / "censo2022" / "isau" / "domicilios"
    raw_ent = paths.raw / "ibge" / "censo2022" / "isau" / "entorno"
    raw_dom.mkdir(parents=True, exist_ok=True)
    raw_ent.mkdir(parents=True, exist_ok=True)

    inspecoes_dom = []
    for url in urls_dom:
        path = _baixar_se_ausente(cliente, url, raw_dom / _nome(url), manifesto)
        inspecoes_dom.append(inspecionar_zip(path))

    inspecoes_entorno = {}
    for universo, url in urls_entorno.items():
        path = _baixar_se_ausente(cliente, url, raw_ent / _nome(url), manifesto)
        inspecoes_entorno[universo] = inspecionar_zip(path)

    mapa_aer = _mapear_variaveis(inspecoes_dom, VARIAVEIS_AER)
    faltantes = sorted(v for v, fontes in mapa_aer.items() if not fontes)
    ambiguas = {v: fontes for v, fontes in mapa_aer.items() if len(fontes) > 1}

    # O snapshot guarda todos os links, nao apenas ZIP. Registrar candidatos a
    # dicionario/documentacao para que o codigo de bueiro seja resolvido por fonte,
    # nunca por memoria ou por inferencia a partir da sequencia V05xxx.
    snap_ent = _carregar_json(
        paths.raw / "ibge" / "indices_publicacao" / "censo2022_entorno_setor.json"
    )
    links_ent = [str(x) for x in snap_ent.get("links", [])]
    candidatos_dicionario = [
        x for x in links_ent
        if any(t in _nome(x).casefold() for t in ("dicion", "document", "nota", "metod", "xlsx", "ods"))
    ]

    status_aer = "RESOLVIDO" if not faltantes and not ambiguas else "PENDENTE"
    qa = {
        "status": "RESOLVIDO_AER_PENDENTE_DRENAGEM" if status_aer == "RESOLVIDO" else "DIAGNOSTICO_ESTRUTURAL",
        "etapa": "05b",
        "arquivos_domiciliares": urls_dom,
        "arquivos_entorno": urls_entorno,
        "inspecao_domicilios": inspecoes_dom,
        "inspecao_entorno": inspecoes_entorno,
        "mapa_variaveis_aer": mapa_aer,
        "variaveis_aer_faltantes": faltantes,
        "variaveis_aer_ambiguas": ambiguas,
        "candidatos_documentacao_entorno": candidatos_dicionario,
        "regra": (
            "A/E/R somente podem ser calculados depois de todas as variaveis requeridas serem "
            "localizadas em cabecalhos oficiais; D somente depois de o codigo de bueiro/boca de lobo "
            "ser comprovado no dicionario/documentacao dos tres universos"
        ),
        "proximo_gate": "05c calcula A/E/R/D e ISAU C4/C3 somente apos resolucao documental da drenagem",
    }
    destino = paths.qa / "etapa05b_inspecao_fontes_isau.json"
    destino.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    registrar_evento(
        manifesto,
        {"tipo": "etapa", "etapa": "05b", "status": qa["status"], "saida": str(destino.relative_to(paths.data_root))},
    )
    print(json.dumps(qa, ensure_ascii=False, indent=2))
