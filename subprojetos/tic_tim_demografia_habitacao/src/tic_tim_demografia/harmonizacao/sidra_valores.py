from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable

import pandas as pd


def _norm(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"\s+", " ", texto).strip().casefold()
    return texto


def normalizar_resposta_sidra(dados: Any) -> pd.DataFrame:
    """Converte uma resposta `/values` com cabeçalho SIDRA em DataFrame legível.

    A API devolve uma lista de objetos e, com ``h/y``, o primeiro objeto contém
    os rótulos das colunas. O parser preserva os valores textuais originais e
    apenas troca as chaves técnicas (NC, D1C, V...) pelos rótulos informados
    pelo próprio SIDRA.
    """
    if not isinstance(dados, list) or len(dados) < 2:
        raise ValueError("Resposta SIDRA vazia ou sem linha de cabeçalho/dados.")
    cabecalho = dados[0]
    if not isinstance(cabecalho, dict):
        raise ValueError("Cabeçalho SIDRA inválido.")

    mapa = {str(chave): str(rotulo) for chave, rotulo in cabecalho.items()}
    linhas = []
    for item in dados[1:]:
        if not isinstance(item, dict):
            continue
        linhas.append({mapa.get(str(k), str(k)): v for k, v in item.items()})
    if not linhas:
        raise ValueError("Resposta SIDRA sem observações após o cabeçalho.")
    return pd.DataFrame(linhas)


def localizar_coluna(
    colunas: Iterable[str],
    *,
    termos_obrigatorios: Iterable[str],
    termos_excluir: Iterable[str] = (),
) -> str:
    obrigatorios = tuple(_norm(x) for x in termos_obrigatorios)
    excluir = tuple(_norm(x) for x in termos_excluir)
    candidatas = []
    for coluna in colunas:
        nome = _norm(coluna)
        if all(t in nome for t in obrigatorios) and not any(t in nome for t in excluir):
            candidatas.append(str(coluna))
    if len(candidatas) != 1:
        raise ValueError(
            f"Coluna SIDRA ambígua/ausente para termos {list(termos_obrigatorios)}; "
            f"candidatas={candidatas}"
        )
    return candidatas[0]


def resolver_colunas_harmonizacao(df: pd.DataFrame, nome_classificacao_idade: str) -> dict[str, str]:
    """Resolve semanticamente as colunas necessárias à harmonização.

    Não depende de D1C/D2C nem da ordem dos descritores. Usa os rótulos
    retornados pelo próprio SIDRA e falha se houver ambiguidade.
    """
    idade_base = _norm(nome_classificacao_idade)
    # Termo distintivo suficientemente estável mesmo quando o descritor usa
    # singular/plural ou pequenas variações de acentuação.
    termo_idade = "idade" if "idade" in idade_base else idade_base
    return {
        "municipio_codigo": localizar_coluna(
            df.columns, termos_obrigatorios=("municipio", "codigo")
        ),
        "municipio_nome": localizar_coluna(
            df.columns,
            termos_obrigatorios=("municipio",),
            termos_excluir=("codigo",),
        ),
        "periodo_codigo": localizar_coluna(
            df.columns, termos_obrigatorios=("periodo", "codigo")
        ),
        "idade_codigo": localizar_coluna(
            df.columns, termos_obrigatorios=(termo_idade, "codigo")
        ),
        "valor": localizar_coluna(df.columns, termos_obrigatorios=("valor",)),
    }


def agregar_bandas_etarias(
    df: pd.DataFrame,
    *,
    colunas: dict[str, str],
    codigo_para_banda: dict[str, str],
    ano_esperado: int,
) -> pd.DataFrame:
    """Agrega categorias etárias SIDRA nas três bandas canônicas.

    Valores especiais/não numéricos provocam erro. A análise histórica não
    transforma símbolos de supressão/ausência em zero.
    """
    work = df.copy()
    work["codigo_ibge"] = work[colunas["municipio_codigo"]].astype(str)
    work["municipio"] = work[colunas["municipio_nome"]].astype(str)
    work["ano"] = pd.to_numeric(work[colunas["periodo_codigo"]], errors="raise").astype(int)
    observados = set(work["ano"].unique().tolist())
    if observados != {int(ano_esperado)}:
        raise ValueError(f"Período SIDRA inesperado: {sorted(observados)} != {[ano_esperado]}")

    work["codigo_idade"] = work[colunas["idade_codigo"]].astype(str)
    work["banda"] = work["codigo_idade"].map(codigo_para_banda)
    desconhecidas = sorted(work.loc[work["banda"].isna(), "codigo_idade"].unique().tolist())
    if desconhecidas:
        raise ValueError(f"Categorias etárias não mapeadas retornadas pelo SIDRA: {desconhecidas}")

    bruto = work[colunas["valor"]].astype(str).str.strip()
    numeric = pd.to_numeric(bruto, errors="coerce")
    invalidos = sorted(bruto[numeric.isna()].unique().tolist())
    if invalidos:
        raise ValueError(
            "Valores SIDRA não numéricos encontrados; ausência/supressão não será convertida em zero: "
            f"{invalidos}"
        )
    work["valor"] = numeric.astype("int64")

    agregado = (
        work.groupby(["codigo_ibge", "municipio", "ano", "banda"], as_index=False)["valor"]
        .sum()
        .pivot(index=["codigo_ibge", "municipio", "ano"], columns="banda", values="valor")
        .reset_index()
    )
    agregado.columns.name = None
    renomear = {
        "0_14": "pop_0_14",
        "15_59": "pop_15_59",
        "60_mais": "pop_60_mais",
    }
    agregado = agregado.rename(columns=renomear)
    esperadas = list(renomear.values())
    faltantes = [c for c in esperadas if c not in agregado.columns]
    if faltantes:
        raise ValueError(f"Bandas ausentes após agregação: {faltantes}")
    if agregado[esperadas].isna().any().any():
        raise ValueError("Há município sem uma das três bandas etárias harmonizadas.")
    agregado["pop_total_harmonizada"] = agregado[esperadas].sum(axis=1)
    return agregado.sort_values(["codigo_ibge", "ano"]).reset_index(drop=True)
