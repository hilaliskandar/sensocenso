"""Etapa 12: QA final do pipeline reprodutível TIC–TIM.

A etapa não recalcula indicadores. Ela consolida os gates já executados,
verifica sequência, estados, universos, checkpoint, invariantes correntes,
cobertura editorial e limitações conhecidas. A reprodutibilidade da edição
corrente é separada da reprodução numérica bit a bit do fechamento histórico.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .paths import resolve_paths
from .proveniencia import registrar_arquivo, registrar_evento


ETAPAS_ESPERADAS = (
    "00", "01", "02a", "02b", "02c", "03a", "03b", "03c", "04",
    "05a", "05b", "05c", "05d", "05e", "06a", "06b", "07", "08",
    "09", "10", "10b", "11a", "11b", "11c", "11d", "11e",
)

STATUS_ACEITOS = {
    "00": {"OK"}, "01": {"OK"}, "02a": {"OK"}, "02b": {"OK"},
    "02c": {"OK"}, "03a": {"OK"}, "03b": {"OK"}, "03c": {"OK"},
    "04": {"OK"}, "05a": {"DIAGNOSTICO_ESTRUTURAL"},
    "05b": {"RESOLVIDO_AER_DRENAGEM"}, "05c": {"OK"}, "05d": {"OK"},
    "05e": {"OK"}, "06a": {"RESOLVIDO_ENTORNO"}, "06b": {"OK"},
    "07": {"OK_COM_DERIVA_EDICAO"}, "08": {"OK_COM_DERIVA_EDICAO"},
    "09": {"OK_COM_DERIVA_EDICAO_E_PENDENCIA_TRANSFORMACAO_MORAN"},
    "10": {"OK_EDICAO_CORRENTE"}, "10b": {"OK_COM_DERIVA_EDICAO"},
    "11a": {"OK_COM_DERIVA_EDICAO"}, "11b": {"OK_EDICAO_CORRENTE"},
    "11c": {"OK"}, "11d": {"OK_COM_DERIVA_EDICAO"},
    "11e": {"OK_COBERTURA_VISUAL"},
}

CHECKPOINT_SHA256 = "72d6490f46c4cef588e2fed7935c69d4d1673c563546f96dfb7683475b13fd6f"
UNIVERSO_URBANO = 9087
UNIVERSO_INTEGRADO = 8073
REFERENCIAS_HISTORICAS = {
    "convergencia_p75": 1255,
    "persistentes_p75_p80": 959,
    "mesmo_vetor": 886,
}
CONTAGENS_CORRENTES = {
    "convergencia_p75": 1304,
    "persistentes_p75_p80": 1016,
    "mesmo_vetor": 945,
}
CONTAGENS_OBSOLETAS = {987, 800}


def _ler_json_obj(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"QA obrigatório ausente: {path}")
    dados = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(dados, dict):
        raise AssertionError(f"QA deve ser objeto JSON: {path}")
    return dados


def _ler_eventos_etapa(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Manifesto de execução ausente: {path}")
    eventos: list[dict[str, Any]] = []
    for numero, linha in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not linha.strip():
            continue
        try:
            registro = json.loads(linha)
        except json.JSONDecodeError as exc:
            raise AssertionError(f"JSONL inválido na linha {numero}: {path}") from exc
        if registro.get("tipo") == "etapa":
            eventos.append(registro)
    return eventos


def validar_sequencia_eventos(eventos: list[dict[str, Any]]) -> dict[str, str]:
    ultimos: dict[str, tuple[int, dict[str, Any]]] = {}
    for indice, evento in enumerate(eventos):
        etapa = str(evento.get("etapa", ""))
        if etapa:
            ultimos[etapa] = (indice, evento)
    faltantes = [e for e in ETAPAS_ESPERADAS if e not in ultimos]
    if faltantes:
        raise AssertionError(f"Etapas ausentes no manifesto: {faltantes}")
    indices = [ultimos[e][0] for e in ETAPAS_ESPERADAS]
    if indices != sorted(indices):
        raise AssertionError("A última ocorrência das etapas não respeita a sequência canônica 00–11e.")
    observados: dict[str, str] = {}
    for etapa in ETAPAS_ESPERADAS:
        status = str(ultimos[etapa][1].get("status", ""))
        observados[etapa] = status
        if status not in STATUS_ACEITOS[etapa]:
            raise AssertionError(
                f"Status inesperado na etapa {etapa}: {status!r}; aceitos={sorted(STATUS_ACEITOS[etapa])}"
            )
    return observados


def _validar_configuracao(paths) -> dict[str, Any]:
    qa00 = _ler_json_obj(paths.qa / "etapa00_configuracao.json")
    qa02b = _ler_json_obj(paths.qa / "etapa02b_harmonizacao_2000_2010.json")
    qa02c = _ler_json_obj(paths.qa / "etapa02c_harmonizacao_2022_urbano.json")
    qa03c = _ler_json_obj(paths.qa / "etapa03c_domicilios_2022_integracao.json")
    if int(qa00.get("municipios", -1)) != 30 or list(qa00.get("anos_censitarios", [])) != [2000, 2010, 2022]:
        raise AssertionError("Etapa 00 divergiu da configuração canônica 30 municípios × três censos.")
    if (int(qa02b.get("linhas", -1)), int(qa02b.get("municipios", -1))) != (60, 30):
        raise AssertionError("Etapa 02b não fecha em 60 linhas/30 municípios.")
    if int(qa02c.get("linhas_longitudinal", -1)) != 90:
        raise AssertionError("Etapa 02c não fecha a base longitudinal 30×3.")
    if int(qa02c.get("setores_urbanos_basico_no_universo", -1)) != UNIVERSO_URBANO:
        raise AssertionError("Etapa 02c divergiu do universo urbano corrente de 9.087 setores.")
    if (int(qa03c.get("linhas", -1)), int(qa03c.get("municipios", -1))) != (90, 30):
        raise AssertionError("Etapa 03c não fecha a base domiciliar 30×3.")
    return {
        "municipios": 30, "anos": [2000, 2010, 2022],
        "linhas_longitudinal": 90, "linhas_domiciliar": 90,
        "universo_urbano": UNIVERSO_URBANO,
    }


def _validar_checkpoint_topologia(paths) -> dict[str, Any]:
    qa09 = _ler_json_obj(paths.qa / "etapa09_validacao_espacial.json")
    checkpoint = qa09.get("checkpoint_universo_integrado", {})
    if int(checkpoint.get("n_setores", -1)) != UNIVERSO_INTEGRADO:
        raise AssertionError("Checkpoint espacial não contém 8.073 setores.")
    if checkpoint.get("sha256_csv") != CHECKPOINT_SHA256:
        raise AssertionError("SHA-256 lógico do checkpoint espacial divergiu.")
    topo = qa09.get("invariantes_topologicos", {})
    esperados = {
        "universo_integrado": 8073,
        "ilhas_queen": 177,
        "arestas_queen_unicas": 19314,
        "arestas_cross_municipais": 304,
    }
    diverg = {k: {"observado": topo.get(k), "esperado": v} for k, v in esperados.items() if topo.get(k) != v}
    if diverg:
        raise AssertionError(f"Invariantes topológicos divergiram: {diverg}")
    pendencia = str(qa09.get("pendencia_moran", "")).strip()
    if not pendencia:
        raise AssertionError("Ressalva histórica de Moran deixou de ser explicitada.")
    candidatos = qa09.get("moran_corrente_candidatos", {})
    if not {"row_standardized", "binary"}.issubset(candidatos):
        raise AssertionError("Candidatos de transformação de Moran não foram preservados no QA.")
    return {
        "checkpoint_sha256": CHECKPOINT_SHA256,
        "universo_integrado": UNIVERSO_INTEGRADO,
        **esperados,
        "moran_ressalva_historica": pendencia,
        "moran_corrente_candidatos": candidatos,
    }


def _validar_invariantes_correntes(paths) -> dict[str, Any]:
    qa07 = _ler_json_obj(paths.qa / "etapa07_familias_analiticas_p75.json")
    qa08 = _ler_json_obj(paths.qa / "etapa08_sensibilidade_p75_p80.json")
    qa10b = _ler_json_obj(paths.qa / "etapa10b_camadas_distributivas.json")
    qa11d = _ler_json_obj(paths.qa / "etapa11d_cartografia_setorial.json")
    qa11e = _ler_json_obj(paths.qa / "etapa11e_manifesto_visual.json")
    if int(qa07.get("universo_integrado_checkpoint", -1)) != UNIVERSO_INTEGRADO:
        raise AssertionError("Etapa 07 divergiu do checkpoint de 8.073 setores.")
    if int(qa07.get("convergencia_p75_corrente", -1)) != 1304:
        raise AssertionError("Convergência P75 corrente divergiu de 1.304.")
    obs08 = qa08.get("observado_corrente", {})
    esperados08 = {
        "convergencia_p75": 1304,
        "persistentes_p75_p80": 1016,
        "mesmo_vetor_entre_persistentes": 945,
    }
    diverg08 = {k: {"observado": obs08.get(k), "esperado": v} for k, v in esperados08.items() if obs08.get(k) != v}
    if diverg08:
        raise AssertionError(f"Sensibilidade P75/P80 divergiu: {diverg08}")
    ref10b = qa10b.get("referencias_regionais_correntes", {})
    if int(qa10b.get("universo_urbano_setores", -1)) != UNIVERSO_URBANO or int(qa10b.get("municipios", -1)) != 30:
        raise AssertionError("Etapa 10b divergiu dos universos canônicos.")
    if abs(float(ref10b.get("pct_preta_parda_30m", -1)) - 0.3974507745638293) > 1e-15:
        raise AssertionError("Participação regional preta+parda divergiu da referência auditada.")
    fcu = qa10b.get("fontes", {}).get("fcu", {})
    if int(fcu.get("setores_fcu_no_universo_30m", -1)) != 557 or int(fcu.get("n_fcu_distintas", -1)) != 236:
        raise AssertionError("Metadados FCU não preservam 557 setores e 236 FCU distintas.")
    inv11d = qa11d.get("invariantes_correntes", {})
    esperados11d = {
        "M04_validos": 7474, "M06_validos": 8067, "M08_convergentes": 1304,
        "M09_persistentes": 1016, "M09_mesmo_vetor": 945, "M12_universo": 9087,
    }
    diverg11d = {k: {"observado": inv11d.get(k), "esperado": v} for k, v in esperados11d.items() if inv11d.get(k) != v}
    if diverg11d:
        raise AssertionError(f"Invariantes cartográficos 11d divergiram: {diverg11d}")
    if qa11e.get("status") != "OK_COBERTURA_VISUAL":
        raise AssertionError("Etapa 11e não fechou com cobertura visual OK.")
    if int(qa11e.get("elementos_planejados", -1)) != 25 or int(qa11e.get("elementos_contabilizados", -1)) != 25 or qa11e.get("faltantes"):
        raise AssertionError("Etapa 11e não fecha os 25 elementos editoriais sem faltantes.")
    if int(qa11e.get("integridade", {}).get("arquivos_auditados", -1)) != 67:
        raise AssertionError("Etapa 11e não registra 67 arquivos auditados.")
    return {
        "correntes": CONTAGENS_CORRENTES,
        "referencias_historicas": REFERENCIAS_HISTORICAS,
        "fcu": {"setores": 557, "fcu_distintas": 236},
        "pct_preta_parda_30m": 0.3974507745638293,
        "cartografia": esperados11d,
        "cobertura_visual": {"elementos": 25, "arquivos_auditados": 67},
    }


def _validar_referencias_nao_obsoletas(paths) -> dict[str, int]:
    qa11e = _ler_json_obj(paths.qa / "etapa11e_manifesto_visual.json")
    refs = qa11e.get("referencias_historicas", {})
    observados = {
        "convergencia_p75": int(refs.get("M08_p75", -1)),
        "persistentes_p75_p80": int(refs.get("M09_persistentes_p80", -1)),
        "mesmo_vetor": int(refs.get("M09_mesmo_vetor", -1)),
    }
    if observados != REFERENCIAS_HISTORICAS:
        raise AssertionError(f"Referências históricas finais divergiram: {observados}")
    if set(observados.values()) & CONTAGENS_OBSOLETAS:
        raise AssertionError(f"Contagem obsoleta reintroduzida como referência estruturada: {observados}")
    return observados


def _resumo_markdown(qa: dict[str, Any]) -> str:
    return "\n".join([
        "# Etapa 12 — QA final do pipeline TIC–TIM", "",
        f"Status: **{qa['status']}**.", "",
        "A edição corrente executou integralmente as etapas 00–11e e preservou universos, checkpoint territorial, invariantes analíticos e cobertura editorial auditados.", "",
        f"- Municípios: {qa['configuracao']['municipios']}.",
        f"- Setores urbanos correntes: {qa['configuracao']['universo_urbano']:,}.".replace(",", "."),
        f"- Setores integrados: {qa['checkpoint_topologia']['universo_integrado']:,}.".replace(",", "."),
        f"- P75 corrente: {qa['invariantes']['correntes']['convergencia_p75']:,}; referência histórica: {qa['invariantes']['referencias_historicas']['convergencia_p75']:,}.".replace(",", "."),
        f"- Persistentes P75–P80 correntes: {qa['invariantes']['correntes']['persistentes_p75_p80']:,}; referência histórica: {qa['invariantes']['referencias_historicas']['persistentes_p75_p80']:,}.".replace(",", "."),
        f"- Mesmo vetor corrente: {qa['invariantes']['correntes']['mesmo_vetor']:,}; referência histórica: {qa['invariantes']['referencias_historicas']['mesmo_vetor']:,}.".replace(",", "."),
        f"- Cobertura editorial: {qa['invariantes']['cobertura_visual']['elementos']} elementos e {qa['invariantes']['cobertura_visual']['arquivos_auditados']} arquivos auditados.", "",
        "## Ressalva histórica preservada", "", qa["ressalvas"][0], "",
        "A ressalva não impede a reprodutibilidade da edição corrente; impede apenas declarar reprodução numérica bit a bit do Moran histórico até a recuperação da transformação/normalização canônica dos pesos.",
    ]) + "\n"


def executar(raiz: Path) -> None:
    raiz = raiz.resolve()
    paths = resolve_paths(raiz)
    paths.create()
    manifesto = paths.manifests / "execucao.jsonl"
    status_eventos = validar_sequencia_eventos(_ler_eventos_etapa(manifesto))
    configuracao = _validar_configuracao(paths)
    checkpoint_topologia = _validar_checkpoint_topologia(paths)
    invariantes = _validar_invariantes_correntes(paths)
    referencias = _validar_referencias_nao_obsoletas(paths)
    qa = {
        "status": "OK_REPRODUTIBILIDADE_CORRENTE_COM_RESSALVA_HISTORICA_MORAN",
        "etapa": "12", "modo": "corrente",
        "sequencia_etapas": list(ETAPAS_ESPERADAS),
        "status_etapas": status_eventos,
        "configuracao": configuracao,
        "checkpoint_topologia": checkpoint_topologia,
        "invariantes": invariantes,
        "referencias_historicas": referencias,
        "ressalvas": [checkpoint_topologia["moran_ressalva_historica"]],
        "criterio_fechamento": "reprodutibilidade da edição corrente validada; derivas de edição e ressalva histórica de Moran explicitadas, sem calibração artificial",
        "pronto_para_revisao_humana": True,
    }
    qa_path = paths.qa / "etapa12_qa_final.json"
    md_path = paths.qa / "etapa12_resumo_final.md"
    qa["saidas"] = [str(qa_path.relative_to(paths.data_root)), str(md_path.relative_to(paths.data_root))]
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_resumo_markdown(qa), encoding="utf-8")
    for path in (qa_path, md_path):
        registrar_arquivo(manifesto, path, origem="Etapa 12 — QA final")
    registrar_evento(manifesto, {
        "tipo": "etapa", "etapa": "12", "status": qa["status"],
        "universo_urbano": UNIVERSO_URBANO, "universo_integrado": UNIVERSO_INTEGRADO,
        "elementos_editoriais": 25, "ressalvas": 1,
    })
    print(json.dumps(qa, ensure_ascii=False, indent=2))
