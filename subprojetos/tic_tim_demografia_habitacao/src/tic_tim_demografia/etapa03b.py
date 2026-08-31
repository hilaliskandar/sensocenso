from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import pandas as pd

from .config import carregar_municipios
from .fontes.sidra import baixar_valores_municipais_em_lotes
from .harmonizacao.sidra_valores import (
    converter_valores_sidra,
    localizar_coluna,
    localizar_coluna_opcional,
    localizar_primeira_alternativa,
    normalizar_resposta_sidra,
)
from .paths import resolve_paths
from .proveniencia import registrar_arquivo, registrar_evento


def _norm(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"\s+", " ", texto).strip().casefold()
    return texto


def _ler_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _carregar_gate_03a(path: Path) -> dict:
    dados = _ler_json(path)
    if not isinstance(dados, dict) or dados.get("status") != "OK":
        raise ValueError("Gate 03a ausente ou inválido; execute novamente --etapa 03a.")
    return dados


def _item_tabela(gate: dict, tabela: int) -> dict:
    itens = [x for x in gate.get("fontes_historicas", []) if int(x.get("tabela", -1)) == tabela]
    if len(itens) != 1:
        raise ValueError(f"Gate 03a deve conter exatamente uma resolução para tabela {tabela}.")
    return itens[0]


def _lotes_esperados(raw_dir: Path, tabela: int) -> list[Path]:
    return [raw_dir / f"t{tabela}_lote_{i:02d}.json" for i in range(1, 4)]


def _adquirir(
    *,
    tabela: int,
    ano: int,
    codigos: list[str],
    raw_dir: Path,
    manifesto: Path,
    classificacoes: dict[str, str | list[str]] | None = None,
) -> list[Path]:
    esperados = _lotes_esperados(raw_dir, tabela)
    if all(p.exists() for p in esperados):
        return esperados
    if any(p.exists() for p in esperados):
        raise RuntimeError(
            f"Aquisição parcial encontrada em {raw_dir}. Remova explicitamente o conjunto "
            "incompleto antes de repetir, para preservar a imutabilidade de raw/."
        )
    return baixar_valores_municipais_em_lotes(
        tabela=tabela,
        codigos_municipais=codigos,
        destino_dir=raw_dir,
        periodos=str(ano),
        variaveis="allxp",
        classificacoes=classificacoes,
        tamanho_lote=10,
        manifesto=manifesto,
    )


def _resolver_colunas_base(df: pd.DataFrame) -> dict[str, str]:
    return {
        "municipio_codigo": localizar_coluna(
            df.columns, termos_obrigatorios=("municipio", "codigo")
        ),
        "municipio_nome": localizar_coluna(
            df.columns, termos_obrigatorios=("municipio",), termos_excluir=("codigo",)
        ),
        "periodo_codigo": localizar_primeira_alternativa(
            df.columns, (("periodo", "codigo"), ("ano", "codigo"))
        ),
        "valor": localizar_coluna(df.columns, termos_obrigatorios=("valor",)),
    }


def _classificar_variavel_156(rotulo: str) -> str | None:
    s = _norm(rotulo)
    if "media de moradores" in s:
        return "tam_medio"
    if "moradores em domicilios particulares ocupados" in s:
        return "moradores_dpo"
    if "domicilios particulares ocupados" in s:
        return "dpo"
    return None


def _parsear_156_lote(path: Path, ano: int) -> pd.DataFrame:
    df = normalizar_resposta_sidra(_ler_json(path))
    cols = _resolver_colunas_base(df)
    variavel = localizar_coluna(
        df.columns, termos_obrigatorios=("variavel",), termos_excluir=("codigo",)
    )
    variavel_codigo = localizar_coluna_opcional(
        df.columns, termos_obrigatorios=("variavel", "codigo")
    )

    work = pd.DataFrame(
        {
            "codigo_ibge": df[cols["municipio_codigo"]].astype(str),
            "municipio": df[cols["municipio_nome"]].astype(str),
            "ano": pd.to_numeric(df[cols["periodo_codigo"]], errors="raise").astype(int),
            "rotulo_variavel": df[variavel].astype(str),
            "valor": converter_valores_sidra(df[cols["valor"]]),
        }
    )
    if variavel_codigo is not None:
        work["codigo_variavel"] = df[variavel_codigo].astype(str)
    if set(work["ano"].unique()) != {ano}:
        raise ValueError(f"Tabela 156 retornou período inesperado no lote {path.name}.")

    work["metrica"] = work["rotulo_variavel"].map(_classificar_variavel_156)
    diagnosticadas = (
        work[["rotulo_variavel", "metrica"]]
        .drop_duplicates()
        .sort_values("rotulo_variavel")
    )
    mapeadas = work[work["metrica"].notna()].copy()
    if mapeadas.empty:
        raise ValueError(
            "Tabela 156 não retornou nenhum dos três conceitos esperados. Rótulos observados: "
            + "; ".join(diagnosticadas["rotulo_variavel"].tolist())
        )

    chaves = ["codigo_ibge", "municipio", "ano", "metrica"]
    if mapeadas.duplicated(chaves).any():
        dup = mapeadas.loc[mapeadas.duplicated(chaves, keep=False), chaves + ["rotulo_variavel"]]
        raise ValueError(
            "Tabela 156 retornou mais de uma observação para município/ano/métrica; "
            f"não haverá escolha silenciosa: {dup.head(20).to_dict('records')}"
        )

    pivot = (
        mapeadas.pivot(index=["codigo_ibge", "municipio", "ano"], columns="metrica", values="valor")
        .reset_index()
    )
    pivot.columns.name = None
    obrig = ["dpo", "moradores_dpo", "tam_medio"]
    faltantes = [c for c in obrig if c not in pivot.columns]
    if faltantes:
        raise ValueError(f"Tabela 156 sem métricas esperadas após parser: {faltantes}")
    if pivot[obrig].isna().any().any():
        raise ValueError("Tabela 156 contém nulos nas métricas domiciliares históricas.")
    return pivot


def _parsear_156(lotes: list[Path], ano: int) -> pd.DataFrame:
    partes = [_parsear_156_lote(p, ano) for p in lotes]
    df = pd.concat(partes, ignore_index=True)
    if df.duplicated(["codigo_ibge", "ano"]).any():
        raise ValueError("Tabela 156 duplicou município/ano entre lotes.")
    return df


def _parsear_185_lote(path: Path, ano: int, gate185: dict) -> pd.DataFrame:
    df = normalizar_resposta_sidra(_ler_json(path))
    cols = _resolver_colunas_base(df)
    nome_classificacao = str(gate185["classificacao_numero_moradores"]["nome"])
    categoria_codigo = localizar_coluna(
        df.columns,
        termos_obrigatorios=(_norm(nome_classificacao), "codigo"),
    )
    valor = converter_valores_sidra(df[cols["valor"]])

    work = pd.DataFrame(
        {
            "codigo_ibge": df[cols["municipio_codigo"]].astype(str),
            "municipio": df[cols["municipio_nome"]].astype(str),
            "ano": pd.to_numeric(df[cols["periodo_codigo"]], errors="raise").astype(int),
            "categoria": df[categoria_codigo].astype(str),
            "valor": valor,
        }
    )
    if set(work["ano"].unique()) != {ano}:
        raise ValueError(f"Tabela 185 retornou período inesperado no lote {path.name}.")

    cat_total = "0"
    cat_um = str(gate185["categoria_um_morador"]["codigo"])
    observadas = set(work["categoria"].unique())
    esperadas = {cat_total, cat_um}
    if observadas != esperadas:
        raise ValueError(
            f"Tabela 185 retornou categorias inesperadas: observadas={sorted(observadas)}, "
            f"esperadas={sorted(esperadas)}"
        )

    total = work[work["categoria"].eq(cat_total)].copy()
    uni = work[work["categoria"].eq(cat_um)].copy()
    for nome, parte in (("total", total), ("um morador", uni)):
        if parte.duplicated(["codigo_ibge", "ano"]).any():
            raise ValueError(f"Tabela 185 duplicou {nome} para município/ano.")

    out = total[["codigo_ibge", "municipio", "ano", "valor"]].rename(
        columns={"valor": "dpp_num_moradores"}
    )
    out = out.merge(
        uni[["codigo_ibge", "ano", "valor"]].rename(columns={"valor": "unipessoais"}),
        on=["codigo_ibge", "ano"],
        how="outer",
        validate="one_to_one",
    )
    out["pct_unipessoais"] = out["unipessoais"] / out["dpp_num_moradores"]
    return out


def _parsear_185(lotes: list[Path], ano: int, gate185: dict) -> pd.DataFrame:
    partes = [_parsear_185_lote(p, ano, gate185) for p in lotes]
    df = pd.concat(partes, ignore_index=True)
    if df.duplicated(["codigo_ibge", "ano"]).any():
        raise ValueError("Tabela 185 duplicou município/ano entre lotes.")
    return df


def executar(raiz: Path) -> None:
    raiz = raiz.resolve()
    paths = resolve_paths(raiz)
    paths.create()
    municipios = carregar_municipios(raiz / "config/municipios.yml")
    codigos = [m.codigo_ibge for m in municipios]
    esperados_codigos = set(codigos)
    manifesto = paths.manifests / "execucao.jsonl"

    gate_path = paths.qa / "etapa03a_selecao_fontes_domicilios.json"
    if not gate_path.exists():
        raise FileNotFoundError(f"Gate 03a ausente: {gate_path}. Execute --etapa 03a.")
    gate = _carregar_gate_03a(gate_path)
    gate185 = _item_tabela(gate, 185)

    if gate185.get("status_resolucao") != "RESOLVIDA":
        raise RuntimeError("Tabela 185 não foi semanticamente resolvida no gate 03a.")

    class_situacao = str(gate185["classificacao_situacao"]["codigo"])
    cat_situacao_total = str(gate185["situacao_total"]["codigo"])
    class_moradores = str(gate185["classificacao_numero_moradores"]["codigo"])
    cat_um = str(gate185["categoria_um_morador"]["codigo"])

    bases = []
    arquivos_brutos: list[str] = []
    for ano in (2000, 2010):
        raw156_dir = paths.raw / "ibge" / "sidra" / "valores" / f"t156_{ano}_domicilios"
        lotes156 = _adquirir(
            tabela=156,
            ano=ano,
            codigos=codigos,
            raw_dir=raw156_dir,
            manifesto=manifesto,
            classificacoes=None,
        )
        arquivos_brutos.extend(str(p.relative_to(paths.data_root)) for p in lotes156)
        b156 = _parsear_156(lotes156, ano)

        raw185_dir = paths.raw / "ibge" / "sidra" / "valores" / f"t185_{ano}_unipessoais"
        lotes185 = _adquirir(
            tabela=185,
            ano=ano,
            codigos=codigos,
            raw_dir=raw185_dir,
            manifesto=manifesto,
            classificacoes={
                class_situacao: cat_situacao_total,
                class_moradores: ["0", cat_um],
            },
        )
        arquivos_brutos.extend(str(p.relative_to(paths.data_root)) for p in lotes185)
        b185 = _parsear_185(lotes185, ano, gate185)

        base = b156.merge(
            b185[["codigo_ibge", "ano", "dpp_num_moradores", "unipessoais", "pct_unipessoais"]],
            on=["codigo_ibge", "ano"],
            how="outer",
            validate="one_to_one",
        )
        bases.append(base)

    historico = pd.concat(bases, ignore_index=True).sort_values(["codigo_ibge", "ano"])
    if len(historico) != 60:
        raise AssertionError(f"Base domiciliar histórica deveria ter 60 linhas; obtidas={len(historico)}")
    observados = set(historico["codigo_ibge"].astype(str))
    if observados != esperados_codigos:
        raise ValueError(
            f"Universo municipal domiciliar diverge da configuração: faltantes={sorted(esperados_codigos-observados)}, "
            f"extras={sorted(observados-esperados_codigos)}"
        )
    if not (historico.groupby("codigo_ibge")["ano"].nunique() == 2).all():
        raise ValueError("Há município sem 2000 e 2010 na base domiciliar histórica.")

    numericas = ["dpo", "moradores_dpo", "tam_medio", "dpp_num_moradores", "unipessoais", "pct_unipessoais"]
    if historico[numericas].isna().any().any():
        raise ValueError("Há lacunas nas métricas domiciliares históricas.")
    if (historico[["dpo", "moradores_dpo", "tam_medio", "dpp_num_moradores"]] <= 0).any().any():
        raise ValueError("DPO, moradores, tamanho médio e universo DPP devem ser positivos.")
    if (historico["unipessoais"] < 0).any() or (historico["unipessoais"] > historico["dpp_num_moradores"]).any():
        raise ValueError("Contagem de unipessoais fora do universo compatível.")
    if not historico["pct_unipessoais"].between(0, 1).all():
        raise ValueError("Participação de unipessoais fora de [0,1].")

    # Gate de coerência intrínseca da Tabela 156. A média publicada pode ter
    # arredondamento, portanto compara-se com moradores/DPO usando tolerância.
    historico["tam_medio_recalculado"] = historico["moradores_dpo"] / historico["dpo"]
    historico["dif_tam_medio"] = historico["tam_medio"] - historico["tam_medio_recalculado"]
    max_abs = float(historico["dif_tam_medio"].abs().max())
    if max_abs > 0.02:
        raise ValueError(
            "Tamanho médio publicado diverge de moradores/DPO acima da tolerância de arredondamento: "
            f"máximo absoluto={max_abs}"
        )

    destino = paths.processed / "municipal"
    destino.mkdir(parents=True, exist_ok=True)
    csv = destino / "base_domiciliar_historica_2000_2010.csv"
    parquet = destino / "base_domiciliar_historica_2000_2010.parquet"
    historico.to_csv(csv, index=False, encoding="utf-8")
    historico.to_parquet(parquet, index=False)
    registrar_arquivo(manifesto, csv, origem="SIDRA tabelas 156 e 185; respostas brutas congeladas")
    registrar_arquivo(manifesto, parquet, origem="SIDRA tabelas 156 e 185; respostas brutas congeladas")

    qa = {
        "status": "OK",
        "linhas": int(len(historico)),
        "municipios": int(historico["codigo_ibge"].nunique()),
        "anos": sorted(int(x) for x in historico["ano"].unique()),
        "metricas": numericas,
        "max_abs_diferenca_tamanho_medio_publicado_recalculado": max_abs,
        "tabela_185": {
            "classificacao_situacao": class_situacao,
            "categoria_situacao_total": cat_situacao_total,
            "classificacao_numero_moradores": class_moradores,
            "categoria_total": "0",
            "categoria_um_morador": cat_um,
        },
        "arquivos_brutos": arquivos_brutos,
        "saida_csv": str(csv.relative_to(paths.data_root)),
        "saida_parquet": str(parquet.relative_to(paths.data_root)),
        "observacao": (
            "Tabela 156 é interpretada pelos rótulos efetivamente retornados na resposta de valores; "
            "Tabela 185 usa somente situação Total e categorias Total/1 morador resolvidas no gate 03a."
        ),
    }
    qa_path = paths.qa / "etapa03b_domicilios_historicos_2000_2010.json"
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    registrar_evento(manifesto, {"tipo": "etapa", "etapa": "03b", **qa})
    print(json.dumps(qa, ensure_ascii=False, indent=2))
