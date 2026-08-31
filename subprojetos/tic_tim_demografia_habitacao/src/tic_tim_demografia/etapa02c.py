from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

from .config import carregar_municipios
from .fontes.censo2022 import (
    agregar_demografia_2022_municipio,
    diagnosticar_simbolos_demografia,
    ler_demografia_setorial_zip,
    ler_setores_urbanos_basico_zip,
)
from .fontes.http import HttpClient
from .paths import resolve_paths
from .proveniencia import registrar_arquivo, registrar_evento
from .qa.regressao import carregar_oraculo_csv, comparar_com_oraculo


PADRAO_BASICO = re.compile(r"^Agregados_por_setores_basico_BR(?:_\d{8})?\.zip$", re.I)
PADRAO_DEMOGRAFIA = re.compile(r"^Agregados_por_setores_demografia_BR(?:_\d{8})?\.zip$", re.I)


def _carregar_links_snapshot(path: Path) -> list[str]:
    dados = json.loads(path.read_text(encoding="utf-8"))
    links = dados.get("links") if isinstance(dados, dict) else None
    if not isinstance(links, list):
        raise ValueError(f"Snapshot de índice inválido: {path}")
    return [str(x) for x in links]


def _selecionar_unico(links: list[str], padrao: re.Pattern[str], descricao: str) -> str:
    candidatos = []
    for link in links:
        nome = Path(urlparse(link).path).name
        if padrao.match(nome):
            candidatos.append(link)
    if len(candidatos) != 1:
        raise ValueError(f"Seleção ambígua/ausente para {descricao}: {candidatos}")
    return candidatos[0]


def _baixar_se_ausente(cliente: HttpClient, url: str, destino: Path, manifesto: Path) -> Path:
    if destino.exists():
        return destino
    return cliente.baixar_arquivo(url, destino, manifesto=manifesto)


def executar(raiz: Path) -> None:
    raiz = raiz.resolve()
    paths = resolve_paths(raiz)
    paths.create()
    municipios = carregar_municipios(raiz / "config/municipios.yml")
    codigos = [m.codigo_ibge for m in municipios]
    referencia = {m.codigo_ibge: (m.nome, m.coroa) for m in municipios}
    manifesto = paths.manifests / "execucao.jsonl"

    base_hist_path = paths.processed / "municipal" / "base_longitudinal_2000_2010.parquet"
    if not base_hist_path.exists():
        raise FileNotFoundError(
            f"Base histórica ausente: {base_hist_path}. Execute primeiro --etapa 02b."
        )

    snapshot = paths.raw / "ibge" / "indices_publicacao" / "censo2022_agregados_setor.json"
    if not snapshot.exists():
        raise FileNotFoundError(f"Snapshot Censo 2022 ausente: {snapshot}. Execute primeiro --etapa 01.")
    links = _carregar_links_snapshot(snapshot)
    url_basico = _selecionar_unico(links, PADRAO_BASICO, "arquivo Básico por setor 2022")
    url_demografia = _selecionar_unico(links, PADRAO_DEMOGRAFIA, "arquivo Demografia por setor 2022")

    raw_dir = paths.raw / "ibge" / "censo2022" / "agregados_setor"
    raw_dir.mkdir(parents=True, exist_ok=True)
    cliente = HttpClient(timeout=600)
    zip_basico = _baixar_se_ausente(
        cliente, url_basico, raw_dir / Path(urlparse(url_basico).path).name, manifesto
    )
    zip_demografia = _baixar_se_ausente(
        cliente, url_demografia, raw_dir / Path(urlparse(url_demografia).path).name, manifesto
    )

    urbanos = ler_setores_urbanos_basico_zip(zip_basico, codigos_municipais=codigos)
    setores = ler_demografia_setorial_zip(
        zip_demografia,
        codigos_municipais=codigos,
        setores_permitidos=urbanos["codigo_setor"],
    )

    set_urbanos = set(urbanos["codigo_setor"].astype(str))
    set_demografia = set(setores["codigo_setor"].astype(str))
    urbanos_sem_demografia = sorted(set_urbanos - set_demografia)

    # O arquivo setorial aplica sigilo em células de baixa frequência. O diagnóstico
    # é sempre preservado, mas a presença de x/X não invalida o processamento:
    # os indicadores etários são agregados somente no universo de setores em que
    # V01031–V01041 estão integralmente divulgadas, reproduzindo a regra usada nos
    # produtos auditados do projeto. Não há imputação, zero artificial ou inferência.
    diagnostico_sigilo = diagnosticar_simbolos_demografia(setores)
    diagnostico_sigilo.update(
        {
            "url_basico": url_basico,
            "url_demografia": url_demografia,
            "setores_urbanos_basico_no_universo": int(len(urbanos)),
            "setores_urbanos_com_demografia": int(len(setores)),
            "setores_urbanos_sem_linha_demografia": int(len(urbanos_sem_demografia)),
            "tratamento_analitico": (
                "complete-case por indicador: para as bandas etárias, usar apenas setores "
                "com V01031–V01041 simultaneamente divulgadas; x/X permanece ausente"
            ),
        }
    )
    diag_path = paths.qa / "etapa02c_sigilo_demografia_2022.json"
    diag_path.write_text(json.dumps(diagnostico_sigilo, ensure_ascii=False, indent=2), encoding="utf-8")
    registrar_evento(
        manifesto,
        {
            "tipo": "diagnostico",
            "etapa": "02c",
            "descricao": "incidência e tratamento de sigilo nos agregados setoriais de demografia 2022",
            "saida": str(diag_path.relative_to(paths.data_root)),
            "setores_com_algum_simbolo": diagnostico_sigilo["setores_com_algum_simbolo"],
            "n_municipios_com_algum_simbolo": diagnostico_sigilo["n_municipios_com_algum_simbolo"],
        },
    )

    base2022 = agregar_demografia_2022_municipio(setores)
    observados = set(base2022["codigo_ibge"].astype(str))
    esperados = set(codigos)
    if observados != esperados:
        raise ValueError(
            "Universo municipal urbano 2022 diverge da configuração: "
            f"faltantes={sorted(esperados-observados)}, extras={sorted(observados-esperados)}"
        )

    base2022["municipio_config"] = base2022["codigo_ibge"].map(lambda x: referencia[str(x)][0])
    base2022["coroa"] = base2022["codigo_ibge"].map(lambda x: referencia[str(x)][1])
    base2022["razao_envelhecimento"] = base2022["pop_60_mais"] / base2022["pop_0_14"] * 100.0

    oraculo_path = raiz / "tests/fixtures/oraculo_2022_urbano_sentinelas.csv"
    regressao2022 = comparar_com_oraculo(base2022, carregar_oraculo_csv(oraculo_path))

    historica = pd.read_parquet(base_hist_path)
    colunas_comuns = [
        "codigo_ibge",
        "ano",
        "pop_0_14",
        "pop_15_59",
        "pop_60_mais",
        "pop_total_harmonizada",
        "municipio_config",
        "coroa",
        "razao_envelhecimento",
    ]
    falt_hist = [c for c in colunas_comuns if c not in historica.columns]
    if falt_hist:
        raise ValueError(f"Base 2000–2010 sem colunas necessárias: {falt_hist}")
    longitudinal = pd.concat(
        [historica[colunas_comuns], base2022[colunas_comuns]], ignore_index=True
    ).sort_values(["codigo_ibge", "ano"]).reset_index(drop=True)

    contagens = longitudinal.groupby("codigo_ibge")["ano"].nunique()
    if len(contagens) != 30 or not (contagens == 3).all():
        raise AssertionError(f"Matriz 30×3 não fechou: {contagens.value_counts().to_dict()}")
    if len(longitudinal) != 90:
        raise AssertionError(f"Base longitudinal deveria ter 90 linhas; observadas={len(longitudinal)}")

    destino_dir = paths.processed / "municipal"
    parquet = destino_dir / "base_longitudinal_2000_2010_2022.parquet"
    csv = destino_dir / "base_longitudinal_2000_2010_2022.csv"
    longitudinal.to_parquet(parquet, index=False)
    longitudinal.to_csv(csv, index=False, encoding="utf-8")
    registrar_arquivo(
        manifesto,
        parquet,
        origem="2000–2010 SIDRA + 2022 agregados setoriais urbanos IBGE, universo etário completo",
    )
    registrar_arquivo(
        manifesto,
        csv,
        origem="2000–2010 SIDRA + 2022 agregados setoriais urbanos IBGE, universo etário completo",
    )

    cobertura = base2022[
        [
            "codigo_ibge",
            "setores_demografia",
            "setores_idade_completa",
            "setores_idade_incompleta",
            "cobertura_setorial_idade",
        ]
    ].copy()
    cobertura["municipio"] = cobertura["codigo_ibge"].map(lambda x: referencia[str(x)][0])
    cobertura = cobertura[
        [
            "codigo_ibge",
            "municipio",
            "setores_demografia",
            "setores_idade_completa",
            "setores_idade_incompleta",
            "cobertura_setorial_idade",
        ]
    ]
    cobertura_path = paths.qa / "etapa02c_cobertura_idade_2022.csv"
    cobertura.to_csv(cobertura_path, index=False, encoding="utf-8")
    registrar_arquivo(manifesto, cobertura_path, origem="Censo 2022 demografia setorial urbana")

    qa = {
        "status": "OK",
        "recorte_2022": "SITUACAO=Urbana no arquivo Básico oficial do Censo 2022",
        "tratamento_sigilo_2022": (
            "universo completo por indicador; bandas 0–14, 15–59 e 60+ usam somente "
            "setores com V01031–V01041 simultaneamente divulgadas; sem imputação"
        ),
        "municipios": int(longitudinal["codigo_ibge"].nunique()),
        "anos": sorted(int(x) for x in longitudinal["ano"].unique()),
        "linhas_longitudinal": int(len(longitudinal)),
        "setores_urbanos_basico_no_universo": int(len(urbanos)),
        "setores_urbanos_com_demografia": int(len(setores)),
        "setores_urbanos_sem_linha_demografia": int(len(urbanos_sem_demografia)),
        "setores_idade_completa": int(base2022["setores_idade_completa"].sum()),
        "setores_idade_incompleta": int(base2022["setores_idade_incompleta"].sum()),
        "cobertura_setorial_idade_min": float(base2022["cobertura_setorial_idade"].min()),
        "cobertura_setorial_idade_max": float(base2022["cobertura_setorial_idade"].max()),
        "amostra_setores_urbanos_sem_demografia": urbanos_sem_demografia[:50],
        "diferenca_fechamento_2022_max_abs": int(base2022["diferenca_fechamento"].abs().max()),
        "regressao_oraculo_2022": regressao2022,
        "url_basico": url_basico,
        "url_demografia": url_demografia,
        "saida_cobertura_csv": str(cobertura_path.relative_to(paths.data_root)),
        "saida_parquet": str(parquet.relative_to(paths.data_root)),
        "saida_csv": str(csv.relative_to(paths.data_root)),
    }
    qa_path = paths.qa / "etapa02c_harmonizacao_2022_urbano.json"
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    registrar_evento(manifesto, {"tipo": "etapa", "etapa": "02c", **qa})
    print(json.dumps(qa, ensure_ascii=False, indent=2))
