"""Etapa 10 em modo corrente: sínteses municipais e correlações.

Reconstrói a síntese municipal relativa denominada ``gravidade físico-urbana``
a partir das edições públicas correntes do Censo 2022, preservando as fórmulas
metodológicas auditadas no fechamento histórico. A etapa também calcula os
quatro pares de correlação de Spearman usados no Relatório Regional.

A síntese físico-urbana é apenas uma medida comparativa entre os 30 municípios.
Ela não representa déficit, percentual de domicílios precários nem prioridade.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from .etapa05c import _arquivo_por_url, _coluna, _ler_csv_zip, _numero, _preparar_setor
from .etapa07 import _contexto_municipal
from .paths import resolve_paths
from .proveniencia import registrar_arquivo, registrar_evento


BLOCOS_COMPOSICIONAIS = {
    "agua_fora_rede": {
        "denominador": ["V00111", "V00112", "V00113", "V00114", "V00115", "V00116", "V00117", "V00118"],
        "numerador": ["V00112", "V00113", "V00114", "V00115", "V00116", "V00117", "V00118"],
        "fonte": "domicilio2",
    },
    "agua_sem_canalizacao": {
        "denominador": ["V00199", "V00200", "V00201"],
        "numerador": ["V00200", "V00201"],
        "fonte": "domicilio2",
    },
    "sem_banheiro_ou_sanitario": {
        "denominador": ["V00232", "V00233", "V00234", "V00235", "V00236", "V00237", "V00238"],
        "numerador": ["V00236", "V00237", "V00238"],
        "fonte": "domicilio2",
    },
    "esgotamento_inadequado": {
        "denominador": ["V00309", "V00310", "V00311", "V00312", "V00313", "V00314", "V00315", "V00316"],
        "numerador": ["V00312", "V00313", "V00314", "V00315", "V00316"],
        "fonte": "domicilio2",
    },
    "residuo_inadequado": {
        "denominador": ["V00397", "V00398", "V00399", "V00400", "V00401", "V00402"],
        "numerador": ["V00399", "V00400", "V00401", "V00402"],
        "fonte": "domicilio2",
    },
    "precariedade_fisica": {
        "denominador": ["V00047", "V00048", "V00049", "V00050", "V00051", "V00052"],
        "numerador": ["V00050", "V00052"],
        "fonte": "domicilio1",
    },
    "domicilios_5mais": {
        "denominador": ["V00017", "V00018", "V00019", "V00020", "V00021", "V00022", "V00023", "V00024", "V00025", "V00026"],
        "numerador": ["V00021", "V00022", "V00023", "V00024", "V00025", "V00026"],
        "fonte": "domicilio1",
    },
}

FISICO_SANITARIOS = [
    "agua_fora_rede",
    "agua_sem_canalizacao",
    "sem_banheiro_ou_sanitario",
    "esgotamento_inadequado",
    "residuo_inadequado",
    "precariedade_fisica",
]
PRESSAO_OCUPACAO = ["domicilios_5mais", "moradores_por_dppo", "pessoas_por_banheiro"]
ATRIBUTOS_ENTORNO = [
    "arborizacao",
    "bueiro_boca_de_lobo",
    "calcada",
    "iluminacao_publica",
    "obstaculo_calcada",
    "pavimentacao",
    "ponto_onibus",
    "rampa_cadeirante",
    "infraestrutura_cicloviaria",
]
UNIVERSOS_ENTORNO = ("domicilios", "moradores", "faces")

REFERENCIAS_RELATORIO = {
    "crescimento_dpo_vs_gravidade_fisico_urbana": {"rho": -0.04, "p_texto": "0,82"},
    "crescimento_dpo_vs_convergencia_setorial": {"rho": 0.10, "p_texto": "0,60"},
    "crescimento_dpo_vs_envelhecimento": {"rho": -0.37, "p_texto": "0,048"},
    "envelhecimento_vs_gravidade_fisico_urbana": {"rho": -0.76, "p_texto": "<0,001"},
}


def _nome_url(url: str) -> str:
    return Path(urlparse(url).path).name


def _selecionar_url(qa05b: dict, token: str) -> str:
    encontrados = [
        str(u)
        for u in qa05b.get("arquivos_domiciliares", [])
        if token.casefold() in _nome_url(str(u)).casefold()
    ]
    if len(encontrados) != 1:
        raise ValueError(f"Fonte domiciliar não resolvida unicamente para token={token}: {encontrados}")
    return encontrados[0]


def _somas_municipais(
    fonte: pd.DataFrame,
    codigo_ibge_por_setor: pd.Series,
    variaveis: list[str],
) -> pd.DataFrame:
    tab = pd.DataFrame(index=fonte.index)
    for var in variaveis:
        tab[var] = _numero(fonte[_coluna(fonte, var)], var)
    tab["codigo_ibge"] = codigo_ibge_por_setor.reindex(tab.index).astype("string")
    if tab["codigo_ibge"].isna().any():
        raise AssertionError("Há setores sem código municipal durante a agregação da etapa 10.")
    return tab.groupby("codigo_ibge", sort=True)[variaveis].sum(min_count=1)


def _proporcao_composicional(
    somas: pd.DataFrame,
    numerador: list[str],
    denominador: list[str],
) -> pd.Series:
    num = somas[numerador].sum(axis=1, min_count=len(numerador))
    den = somas[denominador].sum(axis=1, min_count=len(denominador))
    out = (num / den).where(den.gt(0))
    validos = out.dropna()
    if not validos.between(0, 1).all():
        raise ValueError("Proporção composicional fora de [0,1].")
    return out


def _percentil_relativo(serie: pd.Series) -> pd.Series:
    """Percentil empírico entre municípios, com postos médios em empates."""
    out = pd.Series(np.nan, index=serie.index, dtype="float64")
    validos = pd.to_numeric(serie, errors="coerce").dropna()
    if not validos.empty:
        out.loc[validos.index] = validos.rank(method="average", pct=True)
    return out


def _media_completa(df: pd.DataFrame, colunas: list[str], nome: str) -> pd.Series:
    faltantes = df[colunas].isna().sum(axis=1)
    if faltantes.any():
        amostra = df.index[faltantes.gt(0)].astype(str).tolist()[:10]
        raise ValueError(f"{nome} exige todos os componentes observados; municípios incompletos={amostra}")
    return df[colunas].mean(axis=1)


def _correlacao_spearman(x: pd.Series, y: pd.Series) -> dict[str, float | int]:
    tab = pd.concat([pd.to_numeric(x, errors="coerce"), pd.to_numeric(y, errors="coerce")], axis=1).dropna()
    if len(tab) < 3:
        raise ValueError("Correlação de Spearman exige ao menos três pares válidos.")
    rho, p = spearmanr(tab.iloc[:, 0].to_numpy(), tab.iloc[:, 1].to_numpy())
    return {"n": int(len(tab)), "rho": float(rho), "p_valor": float(p)}


def _agregar_entorno(base_entorno: pd.DataFrame) -> pd.DataFrame:
    base = base_entorno.copy()
    base["codigo_ibge"] = base["codigo_ibge"].astype("string")
    codigos = sorted(base["codigo_ibge"].dropna().unique().tolist())
    out = pd.DataFrame(index=pd.Index(codigos, name="codigo_ibge"))

    for atributo in ATRIBUTOS_ENTORNO:
        por_universo = []
        for universo in UNIVERSOS_ENTORNO:
            prefixo = f"{universo}_{atributo}"
            den_col = f"{prefixo}_den_valido"
            num_col = f"{prefixo}_{'sim' if atributo == 'obstaculo_calcada' else 'nao'}"
            agrupado = base.groupby("codigo_ibge", sort=True)[[num_col, den_col]].sum(min_count=1)
            prevalencia = (agrupado[num_col] / agrupado[den_col]).where(agrupado[den_col].gt(0))
            por_universo.append(prevalencia.rename(universo))
        trio = pd.concat(por_universo, axis=1).reindex(out.index)
        out[f"entorno_{atributo}"] = trio.mean(axis=1, skipna=False)
    return out


def executar(raiz: Path) -> None:
    raiz = raiz.resolve()
    paths = resolve_paths(raiz)
    paths.create()
    manifesto = paths.manifests / "execucao.jsonl"

    arquivos = {
        "longitudinal": paths.processed / "municipal" / "base_longitudinal_2000_2010_2022.parquet",
        "domicilios": paths.processed / "municipal" / "base_domiciliar_2000_2010_2022.parquet",
        "isau": paths.processed / "setorial" / "base_isau_2022.parquet",
        "entorno": paths.processed / "setorial" / "base_entorno_urbano_2022.parquet",
        "familias": paths.processed / "setorial" / "base_familias_analiticas_p75.parquet",
        "qa05b": paths.qa / "etapa05b_inspecao_fontes_isau.json",
    }
    for nome, path in arquivos.items():
        if not path.exists():
            raise FileNotFoundError(f"Pré-requisito 10 ausente ({nome}): {path}")

    longitudinal = pd.read_parquet(arquivos["longitudinal"])
    domicilios = pd.read_parquet(arquivos["domicilios"])
    isau = pd.read_parquet(arquivos["isau"])
    entorno = pd.read_parquet(arquivos["entorno"])
    familias = pd.read_parquet(arquivos["familias"])
    qa05b = json.loads(arquivos["qa05b"].read_text(encoding="utf-8"))

    isau["codigo_setor"] = isau["codigo_setor"].astype("string").str.strip()
    isau["codigo_ibge"] = isau["codigo_ibge"].astype("string").str.strip()
    if len(isau) != 9087 or isau["codigo_setor"].duplicated().any():
        raise AssertionError("Etapa 10 exige o universo urbano corrente de 9.087 setores únicos.")
    indice = pd.Index(isau["codigo_setor"], name="codigo_setor")
    codigo_ibge_por_setor = isau.set_index("codigo_setor")["codigo_ibge"].reindex(indice)
    municipios = (
        isau[["codigo_ibge", "municipio"]]
        .drop_duplicates()
        .sort_values("codigo_ibge")
        .set_index("codigo_ibge")
    )
    if len(municipios) != 30:
        raise AssertionError(f"Síntese municipal exige 30 municípios; obtidos={len(municipios)}")

    raw_dom = paths.raw / "ibge" / "censo2022" / "isau" / "domicilios"
    urls = {
        "domicilio1": _selecionar_url(qa05b, "caracteristicas_domicilio1"),
        "domicilio2": _selecionar_url(qa05b, "caracteristicas_domicilio2"),
        "domicilio3": _selecionar_url(qa05b, "caracteristicas_domicilio3"),
    }
    fontes = {}
    for chave, url in urls.items():
        fontes[chave] = _preparar_setor(
            _ler_csv_zip(_arquivo_por_url(raw_dom, url)), "CD_setor", "CD_SETOR", "setor"
        ).reindex(indice)

    todas_variaveis = {
        chave: sorted(
            {
                var
                for regra in BLOCOS_COMPOSICIONAIS.values()
                if regra["fonte"] == chave
                for var in regra["denominador"]
            }
        )
        for chave in ("domicilio1", "domicilio2")
    }
    todas_variaveis["domicilio1"] += ["V00004", "V00005"]
    todas_variaveis["domicilio2"] += ["V00232", "V00233", "V00234", "V00235"]
    todas_variaveis["domicilio3"] = ["V00552", "V00553", "V00554", "V00555"]
    todas_variaveis = {k: sorted(set(v)) for k, v in todas_variaveis.items()}

    somas = {
        chave: _somas_municipais(fontes[chave], codigo_ibge_por_setor, vars_)
        for chave, vars_ in todas_variaveis.items()
    }

    base = municipios.copy()
    for nome, regra in BLOCOS_COMPOSICIONAIS.items():
        base[nome] = _proporcao_composicional(
            somas[str(regra["fonte"])],
            list(regra["numerador"]),
            list(regra["denominador"]),
        ).reindex(base.index)

    d1 = somas["domicilio1"]
    base["moradores_por_dppo"] = (d1["V00005"] / d1["V00004"]).where(d1["V00004"].gt(0)).reindex(base.index)
    d2 = somas["domicilio2"]
    d3 = somas["domicilio3"]
    moradores_banheiro = d3[["V00552", "V00553", "V00554", "V00555"]].sum(axis=1, min_count=4)
    banheiros_equiv = d2["V00232"] + 2 * d2["V00233"] + 3 * d2["V00234"] + 4 * d2["V00235"]
    base["pessoas_por_banheiro"] = (moradores_banheiro / banheiros_equiv).where(banheiros_equiv.gt(0)).reindex(base.index)

    entorno_municipal = _agregar_entorno(entorno).reindex(base.index)
    base = base.join(entorno_municipal)

    indicadores = FISICO_SANITARIOS + PRESSAO_OCUPACAO + [f"entorno_{a}" for a in ATRIBUTOS_ENTORNO]
    for coluna in indicadores:
        base[f"pctil_{coluna}"] = _percentil_relativo(base[coluna])

    base["gravidade_fisico_sanitaria"] = _media_completa(
        base, [f"pctil_{c}" for c in FISICO_SANITARIOS], "gravidade físico-sanitária"
    )
    base["pressao_ocupacao"] = _media_completa(
        base, [f"pctil_{c}" for c in PRESSAO_OCUPACAO], "pressão de ocupação"
    )
    base["gravidade_entorno"] = _media_completa(
        base, [f"pctil_entorno_{c}" for c in ATRIBUTOS_ENTORNO], "gravidade do entorno"
    )
    base["gravidade_fisico_urbana"] = _media_completa(
        base,
        ["gravidade_fisico_sanitaria", "pressao_ocupacao", "gravidade_entorno"],
        "gravidade físico-urbana",
    )

    contexto = _contexto_municipal(longitudinal, domicilios).set_index("codigo_ibge")
    base["crescimento_dpo_2010_2022"] = contexto["cres_dpo_2010_2022"].reindex(base.index)
    base["razao_envelhecimento_2022"] = contexto["re_2022"].reindex(base.index)

    familias["codigo_ibge"] = familias["codigo_ibge"].astype("string")
    integrado = familias.loc[familias["FLAG_UNIVERSO_INTEGRADO"].fillna(False).astype(bool)].copy()
    if len(integrado) != 8073:
        raise AssertionError(f"Convergência municipal exige checkpoint de 8.073 setores; obtidos={len(integrado)}")
    conv = integrado.groupby("codigo_ibge", sort=True)["CONVERGENCIA_3_OU_4"].agg(
        setores_integrados="size",
        setores_convergentes=lambda s: int(s.eq(1).sum()),
        setores_classificacao_observada=lambda s: int(s.notna().sum()),
    )
    conv["pct_setores_convergencia_3ou4"] = 100.0 * conv["setores_convergentes"] / conv["setores_integrados"]
    base = base.join(conv.reindex(base.index))

    pares = [
        ("crescimento_dpo_vs_gravidade_fisico_urbana", "crescimento_dpo_2010_2022", "gravidade_fisico_urbana"),
        ("crescimento_dpo_vs_convergencia_setorial", "crescimento_dpo_2010_2022", "pct_setores_convergencia_3ou4"),
        ("crescimento_dpo_vs_envelhecimento", "crescimento_dpo_2010_2022", "razao_envelhecimento_2022"),
        ("envelhecimento_vs_gravidade_fisico_urbana", "razao_envelhecimento_2022", "gravidade_fisico_urbana"),
    ]
    correlacoes = []
    for nome, x, y in pares:
        calculada = _correlacao_spearman(base[x], base[y])
        ref = REFERENCIAS_RELATORIO[nome]
        correlacoes.append(
            {
                "par": nome,
                "x": x,
                "y": y,
                **calculada,
                "rho_referencia_relatorio_arredondada": float(ref["rho"]),
                "delta_rho_vs_referencia_arredondada": float(calculada["rho"] - float(ref["rho"])),
                "p_referencia_relatorio": str(ref["p_texto"]),
            }
        )
    correlacoes_df = pd.DataFrame(correlacoes)

    base = base.reset_index()
    out_dir = paths.processed / "municipal"
    csv_path = out_dir / "base_sintese_municipal_2022.csv"
    parquet_path = out_dir / "base_sintese_municipal_2022.parquet"
    base.to_csv(csv_path, index=False, encoding="utf-8")
    base.to_parquet(parquet_path, index=False)
    registrar_arquivo(manifesto, csv_path, origem="Etapa 10 corrente - sínteses municipais")
    registrar_arquivo(manifesto, parquet_path, origem="Etapa 10 corrente - sínteses municipais")

    corr_path = paths.qa / "etapa10_correlacoes_spearman.csv"
    correlacoes_df.to_csv(corr_path, index=False, encoding="utf-8")
    registrar_arquivo(manifesto, corr_path, origem="Etapa 10 corrente - correlações de Spearman")

    qa = {
        "status": "OK_EDICAO_CORRENTE",
        "etapa": "10",
        "modo_execucao": "fontes_correntes_com_referencias_historicas_descritivas",
        "universo_municipal": int(len(base)),
        "universo_urbano_sintese_fisico_urbana": int(len(isau)),
        "universo_integrado_convergencia": int(len(integrado)),
        "fontes_domiciliares": urls,
        "formulas_recuperadas": {
            "precariedade_fisica": "(V00050 + V00052) / soma(V00047..V00052)",
            "domicilios_5mais": "soma(V00021..V00026) / soma(V00017..V00026)",
            "moradores_por_dppo": "V00005 / V00004",
            "pessoas_por_banheiro": "(V00552+V00553+V00554+V00555)/(V00232+2*V00233+3*V00234+4*V00235)",
            "gravidade_fisico_sanitaria": "média dos percentis municipais de 6 indicadores",
            "pressao_ocupacao": "média dos percentis municipais de 3 indicadores",
            "gravidade_entorno": "média dos percentis de 9 precariedades; cada precariedade é antes a média dos 3 universos de entorno",
            "gravidade_fisico_urbana": "média equiponderada de gravidade físico-sanitária, pressão de ocupação e gravidade do entorno",
        },
        "regra_entorno": {
            "obstaculo_calcada": "presença (Sim) representa precariedade",
            "demais_atributos": "ausência (Não) representa precariedade",
            "agregacao": "soma municipal do numerador / soma municipal do denominador válido em cada universo; média simples dos três universos antes do ranqueamento",
        },
        "regra_convergencia": "setores convergentes / todos os setores do checkpoint integrado municipal; NA não é reclassificado como convergente",
        "correlacoes_spearman": correlacoes,
        "referencias_historicas": {
            "natureza": "valores arredondados publicados no Relatório Regional; usados apenas como comparação descritiva, não como gate numérico rígido",
            **REFERENCIAS_RELATORIO,
        },
        "saidas": [
            str(csv_path.relative_to(paths.data_root)),
            str(parquet_path.relative_to(paths.data_root)),
            str(corr_path.relative_to(paths.data_root)),
        ],
    }
    qa_path = paths.qa / "etapa10_sinteses_municipais.json"
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    registrar_arquivo(manifesto, qa_path, origem="Etapa 10 corrente - QA sínteses municipais")
    registrar_evento(
        manifesto,
        {
            "tipo": "etapa",
            "etapa": "10",
            "status": qa["status"],
            "universo_municipal": 30,
            "universo_urbano": int(len(isau)),
            "universo_integrado": int(len(integrado)),
        },
    )
    print(json.dumps(qa, ensure_ascii=False, indent=2))
