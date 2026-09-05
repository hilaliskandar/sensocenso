from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .config import carregar_municipios
from .fontes.sidra import baixar_valores_municipais_em_lotes
from .harmonizacao.sidra_valores import (
    agregar_bandas_etarias,
    normalizar_resposta_sidra,
    resolver_colunas_harmonizacao,
)
from .paths import resolve_paths
from .proveniencia import registrar_arquivo, registrar_evento
from .qa.regressao import carregar_oraculo_csv, comparar_com_oraculo


def _carregar_selecao(path: Path) -> list[dict]:
    dados = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(dados, list) or len(dados) != 2:
        raise ValueError("Seleção SIDRA 2000–2010 inválida; execute novamente a etapa 02a.")
    return dados


def _classificacoes_consulta(item: dict) -> dict[str, list[str] | str]:
    idade_id = str(item["classificacao_idade"]["codigo"])
    categorias_idade = []
    for banda in ("0_14", "15_59", "60_mais"):
        categorias_idade.extend(
            str(x["codigo"]) for x in item["categorias_idade_por_banda"][banda]
        )
    classificacoes: dict[str, list[str] | str] = {idade_id: categorias_idade}

    sexo_id = str(item["classificacao_sexo"]["codigo"])
    classificacoes[sexo_id] = str(item["sexo_total"]["codigo"])

    if item.get("classificacao_situacao") is not None:
        if item.get("situacao_total") is None:
            raise ValueError("Classificação de situação detectada sem categoria Total.")
        situacao_id = str(item["classificacao_situacao"]["codigo"])
        classificacoes[situacao_id] = str(item["situacao_total"]["codigo"])
    return classificacoes


def _mapa_codigo_banda(item: dict) -> dict[str, str]:
    mapa: dict[str, str] = {}
    for banda in ("0_14", "15_59", "60_mais"):
        for categoria in item["categorias_idade_por_banda"][banda]:
            codigo = str(categoria["codigo"])
            if codigo in mapa:
                raise ValueError(f"Categoria etária duplicada entre bandas: {codigo}")
            mapa[codigo] = banda
    return mapa


def _ler_lotes(paths_lotes: list[Path], nome_idade: str, mapa: dict[str, str], ano: int) -> pd.DataFrame:
    partes = []
    for arquivo in paths_lotes:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        df = normalizar_resposta_sidra(dados)
        colunas = resolver_colunas_harmonizacao(df, nome_idade)
        partes.append(
            agregar_bandas_etarias(
                df,
                colunas=colunas,
                codigo_para_banda=mapa,
                ano_esperado=ano,
            )
        )
    combinado = pd.concat(partes, ignore_index=True)
    if combinado.duplicated(["codigo_ibge", "ano"]).any():
        repetidos = combinado.loc[
            combinado.duplicated(["codigo_ibge", "ano"], keep=False),
            ["codigo_ibge", "ano"],
        ].drop_duplicates()
        raise ValueError(f"Municípios duplicados entre lotes SIDRA: {repetidos.to_dict('records')}")
    return combinado


def executar(raiz: Path) -> None:
    raiz = raiz.resolve()
    paths = resolve_paths(raiz)
    paths.create()
    municipios = carregar_municipios(raiz / "config/municipios.yml")
    codigos = [m.codigo_ibge for m in municipios]
    referencia = {m.codigo_ibge: {"municipio_config": m.nome, "coroa": m.coroa} for m in municipios}

    selecao_path = paths.qa / "sidra_selecao_harmonizacao_2000_2010.json"
    if not selecao_path.exists():
        raise FileNotFoundError(
            f"Seleção SIDRA ausente: {selecao_path}. Execute primeiro --etapa 02a."
        )
    selecao = _carregar_selecao(selecao_path)
    manifesto = paths.manifests / "execucao.jsonl"

    bases = []
    arquivos_brutos: list[str] = []
    for item in selecao:
        tabela = int(item["tabela"])
        ano = int(item["periodo"])
        classificacoes = _classificacoes_consulta(item)
        mapa = _mapa_codigo_banda(item)
        raw_dir = paths.raw / "ibge" / "sidra" / "valores" / f"t{tabela}_{ano}"
        esperados = [raw_dir / f"t{tabela}_lote_{i:02d}.json" for i in range(1, 4)]

        if all(p.exists() for p in esperados):
            lotes = esperados
        elif any(p.exists() for p in esperados):
            raise RuntimeError(
                f"Aquisição parcial encontrada em {raw_dir}. Para preservar imutabilidade, "
                "remova explicitamente o conjunto incompleto antes de repetir a etapa."
            )
        else:
            lotes = baixar_valores_municipais_em_lotes(
                tabela=tabela,
                codigos_municipais=codigos,
                destino_dir=raw_dir,
                periodos=str(ano),
                variaveis="allxp",
                classificacoes=classificacoes,
                tamanho_lote=10,
                manifesto=manifesto,
            )

        arquivos_brutos.extend(str(p.relative_to(paths.data_root)) for p in lotes)
        base = _ler_lotes(
            lotes,
            nome_idade=str(item["classificacao_idade"]["nome"]),
            mapa=mapa,
            ano=ano,
        )
        bases.append(base)

    longitudinal = pd.concat(bases, ignore_index=True).sort_values(["codigo_ibge", "ano"])
    observados = set(longitudinal["codigo_ibge"].astype(str))
    esperados_codigos = set(codigos)
    if observados != esperados_codigos:
        raise ValueError(
            "Universo municipal retornado pelo SIDRA diverge da configuração: "
            f"faltantes={sorted(esperados_codigos-observados)}, extras={sorted(observados-esperados_codigos)}"
        )
    contagens = longitudinal.groupby("codigo_ibge")["ano"].nunique()
    if not (contagens == 2).all():
        ruins = contagens[contagens != 2].to_dict()
        raise ValueError(f"Municípios sem os dois censos históricos: {ruins}")

    longitudinal["municipio_config"] = longitudinal["codigo_ibge"].map(
        lambda x: referencia[str(x)]["municipio_config"]
    )
    longitudinal["coroa"] = longitudinal["codigo_ibge"].map(
        lambda x: referencia[str(x)]["coroa"]
    )
    longitudinal["razao_envelhecimento"] = (
        longitudinal["pop_60_mais"] / longitudinal["pop_0_14"] * 100.0
    )

    # Gate independente de regressão. O arquivo de sentinelas é pequeno,
    # versionado e nunca participa dos cálculos; apenas compara resultados.
    oraculo_path = raiz / "tests/fixtures/oraculo_longitudinal_2000_2010_sentinelas.csv"
    if not oraculo_path.exists():
        raise FileNotFoundError(f"Oráculo de regressão versionado ausente: {oraculo_path}")
    regressao = comparar_com_oraculo(longitudinal, carregar_oraculo_csv(oraculo_path))

    destino_dir = paths.processed / "municipal"
    destino_dir.mkdir(parents=True, exist_ok=True)
    parquet = destino_dir / "base_longitudinal_2000_2010.parquet"
    csv = destino_dir / "base_longitudinal_2000_2010.csv"
    longitudinal.to_parquet(parquet, index=False)
    longitudinal.to_csv(csv, index=False, encoding="utf-8")
    registrar_arquivo(manifesto, parquet, origem="derivado das respostas SIDRA brutas congeladas")
    registrar_arquivo(manifesto, csv, origem="derivado das respostas SIDRA brutas congeladas")

    qa = {
        "linhas": int(len(longitudinal)),
        "municipios": int(longitudinal["codigo_ibge"].nunique()),
        "anos": sorted(int(x) for x in longitudinal["ano"].unique()),
        "nulos_bandas": int(
            longitudinal[["pop_0_14", "pop_15_59", "pop_60_mais"]].isna().sum().sum()
        ),
        "regressao_oraculo": regressao,
        "arquivos_brutos": arquivos_brutos,
        "saida_parquet": str(parquet.relative_to(paths.data_root)),
        "saida_csv": str(csv.relative_to(paths.data_root)),
    }
    qa_path = paths.qa / "etapa02b_harmonizacao_2000_2010.json"
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    registrar_evento(
        manifesto,
        {
            "tipo": "etapa",
            "etapa": "02b",
            "status": "OK",
            **qa,
        },
    )
    print(json.dumps(qa, ensure_ascii=False, indent=2))
