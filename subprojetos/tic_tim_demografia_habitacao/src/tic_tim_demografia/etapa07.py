from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .config import carregar_parametros
from .etapa05b import inspecionar_zip
from .etapa05c import _arquivo_por_url, _coluna, _ler_csv_zip, _numero, _preparar_setor
from .paths import resolve_paths
from .proveniencia import registrar_arquivo, registrar_evento


ARRANJO_DENOMINADOR = "V01179"
ARRANJO_NUMERADOR = "V01188"
F3_COLUNAS = {
    "bueiro": "moradores_bueiro_boca_de_lobo_pct_nao",
    "calcada": "moradores_calcada_pct_nao",
    "pavimentacao": "moradores_pavimentacao_pct_nao",
    "iluminacao": "moradores_iluminacao_publica_pct_nao",
    "arvores": "moradores_arborizacao_pct_nao",
}


def _flag_limiar(serie: pd.Series, limiar: float, *, zero_estrito: bool = False) -> pd.Series:
    out = pd.Series(pd.NA, index=serie.index, dtype="Int64")
    validos = serie.notna()
    if zero_estrito and abs(float(limiar)) <= 1e-12:
        out.loc[validos] = serie.loc[validos].gt(0).astype("int64")
    else:
        out.loc[validos] = serie.loc[validos].ge(limiar).astype("int64")
    return out


def _ou_triestado(flags: pd.DataFrame) -> pd.Series:
    """OR que preserva incerteza: 1 domina; 0 exige todos observados; demais casos são NA."""
    out = pd.Series(pd.NA, index=flags.index, dtype="Int64")
    algum_true = flags.eq(1).any(axis=1)
    todos_observados = flags.notna().all(axis=1)
    out.loc[algum_true] = 1
    out.loc[~algum_true & todos_observados] = 0
    return out


def _combinar_familias(flags: pd.DataFrame, minimo: int) -> pd.DataFrame:
    n_true = flags.eq(1).sum(axis=1).astype("Int64")
    n_obs = flags.notna().sum(axis=1).astype("Int64")
    n_na = len(flags.columns) - n_obs
    combinado = pd.Series(pd.NA, index=flags.index, dtype="Int64")
    combinado.loc[n_true.ge(minimo)] = 1
    impossivel = (n_true + n_na).lt(minimo)
    combinado.loc[impossivel] = 0
    return pd.DataFrame(
        {
            "N_FAMILIAS_SINAL": n_true,
            "N_FAMILIAS_OBSERVADAS": n_obs,
            "CONVERGENCIA_3_OU_4": combinado,
        },
        index=flags.index,
    )


def _vetor_familias(linha: pd.Series, colunas: list[str]) -> str:
    ativos = [c for c in colunas if pd.notna(linha[c]) and int(linha[c]) == 1]
    return "+".join(ativos) if ativos else "nenhuma"


def _crescimento(v0: float, v1: float, rotulo: str) -> float:
    if pd.isna(v0) or pd.isna(v1) or float(v0) <= 0:
        raise ValueError(f"Base inválida para crescimento de {rotulo}: v0={v0}, v1={v1}")
    return float(v1) / float(v0) - 1.0


def _linha_ano(df: pd.DataFrame, codigo: str, ano: int) -> pd.Series:
    sub = df.loc[
        df["codigo_ibge"].astype("string").eq(str(codigo))
        & pd.to_numeric(df["ano"], errors="coerce").eq(ano)
    ]
    if len(sub) != 1:
        raise ValueError(f"Esperada uma linha para municipio={codigo}, ano={ano}; obtidas={len(sub)}")
    return sub.iloc[0]


def _contexto_municipal(longitudinal: pd.DataFrame, domicilios: pd.DataFrame) -> pd.DataFrame:
    codigos = sorted(set(longitudinal["codigo_ibge"].astype(str)))
    if codigos != sorted(set(domicilios["codigo_ibge"].astype(str))):
        raise ValueError("Bases longitudinal e domiciliar não possuem o mesmo universo municipal.")

    linhas = []
    for codigo in codigos:
        pop10 = _linha_ano(longitudinal, codigo, 2010)
        pop22 = _linha_ano(longitudinal, codigo, 2022)
        dom10 = _linha_ano(domicilios, codigo, 2010)
        dom22 = _linha_ano(domicilios, codigo, 2022)
        cres_pop = _crescimento(
            float(pop10["pop_total_harmonizada"]),
            float(pop22["pop_total_harmonizada"]),
            "populacao",
        )
        cres_dpo = _crescimento(float(dom10["dpo"]), float(dom22["dpo"]), "DPO")
        linhas.append(
            {
                "codigo_ibge": codigo,
                "municipio": str(dom22["municipio"]),
                "cres_dpo_2010_2022": cres_dpo,
                "cres_pop_2010_2022": cres_pop,
                "diverg_dpo_pop_2010_2022": cres_dpo - cres_pop,
                "re_2022": float(pop22["razao_envelhecimento"]),
                "pct_unipessoais_2022": float(dom22["pct_unipessoais"]),
            }
        )
    out = pd.DataFrame(linhas)
    if len(out) != 30 or out["codigo_ibge"].nunique() != 30:
        raise AssertionError("Contexto municipal das famílias não fechou em 30 municípios.")
    return out


def _selecionar_arranjo(qa05b: dict, raw_dir: Path) -> tuple[Path, str]:
    encontrados: list[tuple[Path, str]] = []
    for url in qa05b.get("arquivos_domiciliares", []):
        path = _arquivo_por_url(raw_dir, str(url))
        info = inspecionar_zip(path)
        for csv_info in info["csvs"]:
            cols = set(csv_info["colunas"])
            if {ARRANJO_DENOMINADOR, ARRANJO_NUMERADOR} <= cols:
                encontrados.append((path, str(url)))
                break
    if len(encontrados) != 1:
        nomes = [p.name for p, _ in encontrados]
        raise ValueError(
            "V01179/V01188 devem ocorrer conjuntamente em um único agregado domiciliar; "
            f"candidatos={nomes}"
        )
    return encontrados[0]


def _arranjo_setorial(path: Path, setores: pd.Index) -> pd.DataFrame:
    fonte = _preparar_setor(_ler_csv_zip(path), "CD_setor", "CD_SETOR", "setor")
    fonte = fonte.reindex(setores)
    den = _numero(fonte[_coluna(fonte, ARRANJO_DENOMINADOR)], ARRANJO_DENOMINADOR)
    num = _numero(fonte[_coluna(fonte, ARRANJO_NUMERADOR)], ARRANJO_NUMERADOR)
    ambos = den.notna() & num.notna()
    inconsistentes = ambos & (num > den)
    if inconsistentes.any():
        amostra = fonte.index[inconsistentes].astype(str).tolist()[:20]
        raise ValueError(f"V01188 excede V01179 em setores: {amostra}")
    pct = (num / den).where(ambos & den.gt(0))
    validos = pct.dropna()
    if not validos.between(0, 1).all():
        raise ValueError("Proporção de responsável mulher sem cônjuge fora de [0,1].")
    return pd.DataFrame(
        {
            "v01179_domicilios_sem_conjuge": den,
            "v01188_resp_mulher_sem_conjuge": num,
            "pct_sem_conjuge_resp_mulher_2022": pct,
        },
        index=setores,
    )


def _limiar(serie: pd.Series, q: float, nome: str) -> float:
    validos = pd.to_numeric(serie, errors="coerce").dropna()
    if validos.empty:
        raise ValueError(f"Sem observações válidas para calcular {nome}.")
    return float(validos.quantile(q))


def _comparar_referencias(calculados: dict[str, float], referencias: dict) -> dict:
    out = {}
    for chave, valor in calculados.items():
        ref = referencias.get(chave)
        out[chave] = {
            "calculado": float(valor),
            "referencia_caderno": float(ref) if ref is not None else None,
            "diferenca_abs": abs(float(valor) - float(ref)) if ref is not None else None,
        }
    return out


def executar(raiz: Path) -> None:
    raiz = raiz.resolve()
    paths = resolve_paths(raiz)
    paths.create()
    manifesto = paths.manifests / "execucao.jsonl"
    parametros = carregar_parametros(raiz / "config/parametros.yml")
    q = float(parametros["territorializacao"]["percentil_principal"])
    minimo = int(parametros["territorializacao"]["minimo_familias_convergencia"])
    qa_ref = parametros.get("qa_referencia", {})
    esperado_integrado = int(qa_ref.get("setores_universo_final", 8073))

    arquivos = {
        "longitudinal": paths.processed / "municipal" / "base_longitudinal_2000_2010_2022.parquet",
        "domicilios": paths.processed / "municipal" / "base_domiciliar_2000_2010_2022.parquet",
        "cwr": paths.processed / "setorial" / "base_renovacao_demografica_2022.parquet",
        "isau": paths.processed / "setorial" / "base_isau_2022.parquet",
        "exposicao": paths.processed / "setorial" / "base_isau_priorizacao_2022.parquet",
        "entorno": paths.processed / "setorial" / "base_entorno_urbano_2022.parquet",
        "qa05b": paths.qa / "etapa05b_inspecao_fontes_isau.json",
    }
    for nome, path in arquivos.items():
        if not path.exists():
            raise FileNotFoundError(f"Pré-requisito 07 ausente ({nome}): {path}")

    longitudinal = pd.read_parquet(arquivos["longitudinal"])
    domicilios = pd.read_parquet(arquivos["domicilios"])
    cwr = pd.read_parquet(arquivos["cwr"])
    isau = pd.read_parquet(arquivos["isau"])
    exposicao = pd.read_parquet(arquivos["exposicao"])
    entorno = pd.read_parquet(arquivos["entorno"])

    base = isau.copy()
    base["codigo_setor"] = base["codigo_setor"].astype("string").str.strip()
    if len(base) != 9087 or base["codigo_setor"].duplicated().any():
        raise AssertionError("Etapa 07 exige o universo urbano canônico inicial de 9.087 setores únicos.")
    indice = pd.Index(base["codigo_setor"], name="codigo_setor")

    cwr_cols = ["codigo_setor", "cwr_0_4_por_1000_m1549"]
    entorno_cols = ["codigo_setor", "F3_ENTORNO_ALTO"] + list(F3_COLUNAS.values())
    expo_cols = ["codigo_setor", "POP_TOTAL", "DPPO"]
    base = base.merge(cwr[cwr_cols], on="codigo_setor", how="left", validate="one_to_one")
    base = base.merge(exposicao[expo_cols], on="codigo_setor", how="left", validate="one_to_one")
    base = base.merge(entorno[entorno_cols], on="codigo_setor", how="left", validate="one_to_one")

    # O universo integrado do fechamento combina observabilidade C3 e exposição
    # populacional/domiciliar. Os percentis setoriais da territorialização são
    # calculados nesse universo; ausências das demais dimensões permanecem NA.
    base["FLAG_UNIVERSO_INTEGRADO"] = (
        base["PRIV_C3"].notna() & base["POP_TOTAL"].notna() & base["DPPO"].notna()
    )
    if int(base["FLAG_UNIVERSO_INTEGRADO"].sum()) != esperado_integrado:
        raise AssertionError(
            "Gate do universo integrado não reproduziu o fechamento: "
            f"{int(base['FLAG_UNIVERSO_INTEGRADO'].sum())} != {esperado_integrado}. "
            "Não recortar manualmente; investigar cobertura e joins."
        )

    qa05b = json.loads(arquivos["qa05b"].read_text(encoding="utf-8"))
    raw_dom = paths.raw / "ibge" / "censo2022" / "isau" / "domicilios"
    arranjo_path, arranjo_url = _selecionar_arranjo(qa05b, raw_dom)
    arranjo = _arranjo_setorial(arranjo_path, indice).reset_index()
    base = base.merge(arranjo, on="codigo_setor", how="left", validate="one_to_one")

    contexto = _contexto_municipal(longitudinal, domicilios)
    contexto_idx = contexto.set_index("codigo_ibge")
    for coluna in contexto.columns:
        if coluna in ("codigo_ibge", "municipio"):
            continue
        base[coluna] = base["codigo_ibge"].astype(str).map(contexto_idx[coluna])

    base["sem_bueiro"] = base[F3_COLUNAS["bueiro"]] / 100.0
    base["sem_calcada"] = base[F3_COLUNAS["calcada"]] / 100.0
    base["sem_pavimentacao"] = base[F3_COLUNAS["pavimentacao"]] / 100.0
    base["sem_iluminacao"] = base[F3_COLUNAS["iluminacao"]] / 100.0
    base["sem_arvores"] = base[F3_COLUNAS["arvores"]] / 100.0
    integrado = base.loc[base["FLAG_UNIVERSO_INTEGRADO"]].copy()

    limiares = {
        "crescimento_dpo": _limiar(contexto["cres_dpo_2010_2022"], q, "crescimento DPO"),
        "divergencia_dpo_pop": _limiar(
            contexto["diverg_dpo_pop_2010_2022"], q, "divergência DPO-população"
        ),
        "cwr": _limiar(integrado["cwr_0_4_por_1000_m1549"], q, "CWR"),
        "privacao": _limiar(integrado["PRIV_C3"], q, "privação ISAU"),
        "re_60_0_14": _limiar(contexto["re_2022"], q, "razão de envelhecimento"),
        "unipessoais": _limiar(contexto["pct_unipessoais_2022"], q, "unipessoais"),
        "resp_mulher_sem_conjuge": _limiar(
            integrado["pct_sem_conjuge_resp_mulher_2022"], q, "responsável mulher sem cônjuge"
        ),
        "sem_bueiro": _limiar(integrado["sem_bueiro"], q, "sem bueiro"),
        "sem_calcada": _limiar(integrado["sem_calcada"], q, "sem calçada"),
        "sem_pavimentacao": _limiar(integrado["sem_pavimentacao"], q, "sem pavimentação"),
        "sem_iluminacao": _limiar(integrado["sem_iluminacao"], q, "sem iluminação"),
        "sem_arvores": _limiar(integrado["sem_arvores"], q, "sem árvores"),
    }

    base["F1_CTX_CRES_DPO_P75"] = _flag_limiar(
        base["cres_dpo_2010_2022"], limiares["crescimento_dpo"]
    )
    base["F1_CTX_DIVERG_P75"] = _flag_limiar(
        base["diverg_dpo_pop_2010_2022"], limiares["divergencia_dpo_pop"]
    )
    base["F1_LOCAL_CWR_P75"] = _flag_limiar(base["cwr_0_4_por_1000_m1549"], limiares["cwr"])
    base["F1"] = _ou_triestado(
        base[["F1_CTX_CRES_DPO_P75", "F1_CTX_DIVERG_P75", "F1_LOCAL_CWR_P75"]]
    )

    base["F2_LOCAL_PRIV_P75"] = _flag_limiar(base["PRIV_C3"], limiares["privacao"])
    base["F2"] = base["F2_LOCAL_PRIV_P75"].astype("Int64")

    f3_flags = []
    for nome in ("bueiro", "calcada", "pavimentacao", "iluminacao", "arvores"):
        coluna = f"F3_LOCAL_SEM_{nome.upper()}_P75"
        base[coluna] = _flag_limiar(
            base[f"sem_{nome}"], limiares[f"sem_{nome}"], zero_estrito=True
        )
        f3_flags.append(coluna)
    f3_tab = base[f3_flags]
    base["F3_N_COMPONENTES_OBS"] = f3_tab.notna().sum(axis=1).astype("Int64")
    base["F3_N_COMPONENTES_ALTOS"] = f3_tab.eq(1).sum(axis=1).astype("Int64")
    base["F3"] = pd.Series(pd.NA, index=base.index, dtype="Int64")
    completos_f3 = base["F3_N_COMPONENTES_OBS"].eq(5)
    base.loc[completos_f3, "F3"] = (
        base.loc[completos_f3, "F3_N_COMPONENTES_ALTOS"].ge(2).astype("int64")
    )
    comparavel_f3 = base["F3"].notna() & base["F3_ENTORNO_ALTO"].notna()
    diverg_f3 = int(
        base.loc[comparavel_f3, "F3"].astype(int).ne(
            base.loc[comparavel_f3, "F3_ENTORNO_ALTO"].astype(int)
        ).sum()
    )

    base["F4_CTX_RE_P75"] = _flag_limiar(base["re_2022"], limiares["re_60_0_14"])
    base["F4_CTX_UNIP_P75"] = _flag_limiar(
        base["pct_unipessoais_2022"], limiares["unipessoais"]
    )
    base["F4_LOCAL_RESP_MULHER_P75"] = _flag_limiar(
        base["pct_sem_conjuge_resp_mulher_2022"], limiares["resp_mulher_sem_conjuge"]
    )
    base["F4"] = _ou_triestado(
        base[["F4_CTX_RE_P75", "F4_CTX_UNIP_P75", "F4_LOCAL_RESP_MULHER_P75"]]
    )

    familias = base[["F1", "F2", "F3", "F4"]]
    combinacao = _combinar_familias(familias, minimo)
    for coluna in combinacao.columns:
        base[coluna] = combinacao[coluna]
    base["VETOR_FAMILIAS"] = familias.apply(
        lambda r: _vetor_familias(r, ["F1", "F2", "F3", "F4"]), axis=1
    )

    integrado = base.loc[base["FLAG_UNIVERSO_INTEGRADO"]].copy()
    cobertura_integrada = {
        "cwr": int(integrado["cwr_0_4_por_1000_m1549"].notna().sum()),
        "privacao": int(integrado["PRIV_C3"].notna().sum()),
        "entorno_5_componentes": int(integrado["F3"].notna().sum()),
        "resp_mulher_sem_conjuge": int(
            integrado["pct_sem_conjuge_resp_mulher_2022"].notna().sum()
        ),
    }
    esperados_cobertura = {
        "cwr": 7474,
        "privacao": 8073,
        "entorno_5_componentes": 8052,
        "resp_mulher_sem_conjuge": 7983,
    }
    diverg_cobertura = {
        k: {"observado": cobertura_integrada[k], "esperado": v}
        for k, v in esperados_cobertura.items()
        if cobertura_integrada[k] != v
    }
    if diverg_cobertura:
        raise AssertionError(f"Coberturas do universo integrado divergiram: {diverg_cobertura}")

    contagens_componentes = {
        "cwr_p75": int(integrado["F1_LOCAL_CWR_P75"].eq(1).sum()),
        "privacao_p75": int(integrado["F2"].eq(1).sum()),
        "entorno_f3_p75": int(integrado["F3"].eq(1).sum()),
        "resp_mulher_p75": int(integrado["F4_LOCAL_RESP_MULHER_P75"].eq(1).sum()),
    }
    esperados_componentes = {
        "cwr_p75": 1870,
        "privacao_p75": 2019,
        "entorno_f3_p75": 2014,
        "resp_mulher_p75": 1998,
    }
    diverg_componentes = {
        k: {"observado": contagens_componentes[k], "esperado": v}
        for k, v in esperados_componentes.items()
        if contagens_componentes[k] != v
    }
    if diverg_componentes:
        raise AssertionError(f"Contagens P75 do fechamento divergiram: {diverg_componentes}")

    convergencia_integrada = int(integrado["CONVERGENCIA_3_OU_4"].eq(1).sum())
    esperado_convergencia = int(qa_ref.get("setores_convergentes_p75", 1255))
    if convergencia_integrada != esperado_convergencia:
        raise AssertionError(
            "Convergência P75 no universo integrado divergiu do fechamento: "
            f"{convergencia_integrada} != {esperado_convergencia}"
        )

    out_dir = paths.processed / "setorial"
    csv_path = out_dir / "base_familias_analiticas_p75.csv"
    parquet_path = out_dir / "base_familias_analiticas_p75.parquet"
    base.to_csv(csv_path, index=False, encoding="utf-8")
    base.to_parquet(parquet_path, index=False)
    registrar_arquivo(manifesto, csv_path, origem="Etapa 07 - quatro famílias analíticas P75")
    registrar_arquivo(manifesto, parquet_path, origem="Etapa 07 - quatro famílias analíticas P75")

    referencias = qa_ref.get("limiares_p75", {})
    qa = {
        "status": "OK",
        "etapa": "07",
        "universo_base_setores": int(len(base)),
        "universo_integrado": int(base["FLAG_UNIVERSO_INTEGRADO"].sum()),
        "regra_universo_integrado": "PRIV_C3, POP_TOTAL e DPPO observáveis",
        "percentil": q,
        "minimo_familias_convergencia": minimo,
        "fonte_arranjo": {"arquivo": arranjo_path.name, "url": arranjo_url},
        "formula_arranjo": "V01188 / V01179 quando ambos publicados e V01179 > 0",
        "limiares": limiares,
        "comparacao_limiares_caderno": _comparar_referencias(limiares, referencias),
        "cobertura_integrada": cobertura_integrada,
        "contagens_componentes_integradas": contagens_componentes,
        "familias_sinalizadas_integradas": {
            f: int(integrado[f].eq(1).sum()) for f in ("F1", "F2", "F3", "F4")
        },
        "convergencia_integrada": convergencia_integrada,
        "qa_f3_divergencias_com_06b": diverg_f3,
        "politica_ausencias": (
            "ausência/sigilo permanece NA; família é 1 se algum componente observado é 1, "
            "0 somente quando todos os seus componentes estão observados e são 0"
        ),
        "cautela": (
            "F1 e F4 combinam contexto municipal com marcador local; a propagação do contexto "
            "municipal aos setores não o transforma em observação microlocal."
        ),
        "saidas": [
            str(csv_path.relative_to(paths.data_root)),
            str(parquet_path.relative_to(paths.data_root)),
        ],
    }
    qa_path = paths.qa / "etapa07_familias_analiticas_p75.json"
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    registrar_arquivo(manifesto, qa_path, origem="Etapa 07 - QA quatro famílias P75")
    registrar_evento(
        manifesto,
        {
            "tipo": "etapa",
            "etapa": "07",
            "status": "OK",
            "universo": int(len(base)),
            "universo_integrado": esperado_integrado,
            "convergencia_p75": convergencia_integrada,
        },
    )
    print(json.dumps(qa, ensure_ascii=False, indent=2))
