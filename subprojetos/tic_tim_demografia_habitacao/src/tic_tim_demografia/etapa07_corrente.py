"""Etapa 07 em modo de fontes públicas correntes.

O pertencimento ao universo integrado permanece rigidamente definido pelo
checkpoint histórico Gate18G7F2. Já os valores temáticos reconstruídos a partir
das edições públicas correntes são tratados como edição observada: divergências
em cobertura, limiares e contagens são registradas no QA, mas não redefinem o
universo e não são artificialmente corrigidas para reproduzir o passado.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .config import carregar_parametros
from .etapa07 import (
    F3_COLUNAS,
    _arranjo_setorial,
    _combinar_familias,
    _comparar_referencias,
    _contexto_municipal,
    _flag_limiar,
    _limiar,
    _ou_triestado,
    _selecionar_arranjo,
    _vetor_familias,
)
from .paths import resolve_paths
from .proveniencia import registrar_arquivo, registrar_evento
from .universo_integrado import carregar_universo_integrado_canonico


REFERENCIAS_COBERTURA = {
    "cwr": 7474,
    "privacao": 8073,
    "entorno_5_componentes": 8052,
    "resp_mulher_sem_conjuge": 7983,
}
REFERENCIAS_COMPONENTES_P75 = {
    "cwr_p75": 1870,
    "privacao_p75": 2019,
    "entorno_f3_p75": 2014,
    "resp_mulher_p75": 1998,
}


def _comparar_contagens(observado: dict[str, int], esperado: dict[str, int]) -> dict[str, dict[str, int]]:
    return {
        chave: {
            "observado_corrente": int(observado.get(chave, 0)),
            "referencia_historica": int(valor),
            "delta": int(observado.get(chave, 0)) - int(valor),
        }
        for chave, valor in esperado.items()
    }


def _tem_deriva(comparacao: dict[str, dict[str, int]]) -> bool:
    return any(int(v["delta"]) != 0 for v in comparacao.values())


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
        raise AssertionError("Etapa 07 exige o universo urbano inicial de 9.087 setores únicos.")
    indice = pd.Index(base["codigo_setor"], name="codigo_setor")

    base = base.merge(
        cwr[["codigo_setor", "cwr_0_4_por_1000_m1549"]],
        on="codigo_setor", how="left", validate="one_to_one",
    )
    base = base.merge(
        exposicao[["codigo_setor", "POP_TOTAL", "DPPO"]],
        on="codigo_setor", how="left", validate="one_to_one",
    )
    entorno_cols = ["codigo_setor", "F3_ENTORNO_ALTO"] + list(F3_COLUNAS.values())
    base = base.merge(entorno[entorno_cols], on="codigo_setor", how="left", validate="one_to_one")

    checkpoint, checkpoint_meta = carregar_universo_integrado_canonico(
        paths.raw, esperado=esperado_integrado
    )
    codigos_checkpoint = set(checkpoint["codigo_setor"].astype(str))
    codigos_base = set(base["codigo_setor"].astype(str))
    ausentes_checkpoint = sorted(codigos_checkpoint - codigos_base)
    if ausentes_checkpoint:
        raise AssertionError(
            "Checkpoint Gate18G7F2 contém setores ausentes da base urbana corrente: "
            f"n={len(ausentes_checkpoint)}; amostra={ausentes_checkpoint[:20]}"
        )
    base["FLAG_UNIVERSO_INTEGRADO"] = base["codigo_setor"].astype(str).isin(codigos_checkpoint)
    if int(base["FLAG_UNIVERSO_INTEGRADO"].sum()) != esperado_integrado:
        raise AssertionError("Pertencimento ao checkpoint histórico deixou de fechar em 8.073 setores.")

    qa05b = json.loads(arquivos["qa05b"].read_text(encoding="utf-8"))
    raw_dom = paths.raw / "ibge" / "censo2022" / "isau" / "domicilios"
    arranjo_path, arranjo_url = _selecionar_arranjo(qa05b, raw_dom)
    arranjo = _arranjo_setorial(arranjo_path, indice).reset_index()
    base = base.merge(arranjo, on="codigo_setor", how="left", validate="one_to_one")

    contexto = _contexto_municipal(longitudinal, domicilios)
    contexto_idx = contexto.set_index("codigo_ibge")
    for coluna in contexto.columns:
        if coluna not in ("codigo_ibge", "municipio"):
            base[coluna] = base["codigo_ibge"].astype(str).map(contexto_idx[coluna])

    for nome, coluna in F3_COLUNAS.items():
        base[f"sem_{nome}"] = base[coluna] / 100.0
    integrado = base.loc[base["FLAG_UNIVERSO_INTEGRADO"]].copy()

    limiares = {
        "crescimento_dpo": _limiar(contexto["cres_dpo_2010_2022"], q, "crescimento DPO"),
        "divergencia_dpo_pop": _limiar(contexto["diverg_dpo_pop_2010_2022"], q, "divergência DPO-população"),
        "cwr": _limiar(integrado["cwr_0_4_por_1000_m1549"], q, "CWR"),
        "privacao": _limiar(integrado["PRIV_C3"], q, "privação ISAU"),
        "re_60_0_14": _limiar(contexto["re_2022"], q, "razão de envelhecimento"),
        "unipessoais": _limiar(contexto["pct_unipessoais_2022"], q, "unipessoais"),
        "resp_mulher_sem_conjuge": _limiar(integrado["pct_sem_conjuge_resp_mulher_2022"], q, "responsável mulher sem cônjuge"),
        **{f"sem_{nome}": _limiar(integrado[f"sem_{nome}"], q, f"sem {nome}") for nome in F3_COLUNAS},
    }

    base["F1_CTX_CRES_DPO_P75"] = _flag_limiar(base["cres_dpo_2010_2022"], limiares["crescimento_dpo"])
    base["F1_CTX_DIVERG_P75"] = _flag_limiar(base["diverg_dpo_pop_2010_2022"], limiares["divergencia_dpo_pop"])
    base["F1_LOCAL_CWR_P75"] = _flag_limiar(base["cwr_0_4_por_1000_m1549"], limiares["cwr"])
    base["F1"] = _ou_triestado(base[["F1_CTX_CRES_DPO_P75", "F1_CTX_DIVERG_P75", "F1_LOCAL_CWR_P75"]])

    base["F2_LOCAL_PRIV_P75"] = _flag_limiar(base["PRIV_C3"], limiares["privacao"])
    base["F2"] = base["F2_LOCAL_PRIV_P75"].astype("Int64")

    f3_flags: list[str] = []
    for nome in F3_COLUNAS:
        coluna = f"F3_LOCAL_SEM_{nome.upper()}_P75"
        base[coluna] = _flag_limiar(base[f"sem_{nome}"], limiares[f"sem_{nome}"], zero_estrito=True)
        f3_flags.append(coluna)
    f3_tab = base[f3_flags]
    base["F3_N_COMPONENTES_OBS"] = f3_tab.notna().sum(axis=1).astype("Int64")
    base["F3_N_COMPONENTES_ALTOS"] = f3_tab.eq(1).sum(axis=1).astype("Int64")
    base["F3"] = pd.Series(pd.NA, index=base.index, dtype="Int64")
    completos_f3 = base["F3_N_COMPONENTES_OBS"].eq(5)
    base.loc[completos_f3, "F3"] = base.loc[completos_f3, "F3_N_COMPONENTES_ALTOS"].ge(2).astype("int64")
    comparavel_f3 = base["F3"].notna() & base["F3_ENTORNO_ALTO"].notna()
    diverg_f3 = int(base.loc[comparavel_f3, "F3"].astype(int).ne(base.loc[comparavel_f3, "F3_ENTORNO_ALTO"].astype(int)).sum())

    base["F4_CTX_RE_P75"] = _flag_limiar(base["re_2022"], limiares["re_60_0_14"])
    base["F4_CTX_UNIP_P75"] = _flag_limiar(base["pct_unipessoais_2022"], limiares["unipessoais"])
    base["F4_LOCAL_RESP_MULHER_P75"] = _flag_limiar(base["pct_sem_conjuge_resp_mulher_2022"], limiares["resp_mulher_sem_conjuge"])
    base["F4"] = _ou_triestado(base[["F4_CTX_RE_P75", "F4_CTX_UNIP_P75", "F4_LOCAL_RESP_MULHER_P75"]])

    familias = base[["F1", "F2", "F3", "F4"]]
    combinacao = _combinar_familias(familias, minimo)
    for coluna in combinacao.columns:
        base[coluna] = combinacao[coluna]
    base["VETOR_FAMILIAS"] = familias.apply(lambda r: _vetor_familias(r, ["F1", "F2", "F3", "F4"]), axis=1)

    integrado = base.loc[base["FLAG_UNIVERSO_INTEGRADO"]].copy()
    cobertura = {
        "cwr": int(integrado["cwr_0_4_por_1000_m1549"].notna().sum()),
        "privacao": int(integrado["PRIV_C3"].notna().sum()),
        "entorno_5_componentes": int(integrado["F3"].notna().sum()),
        "resp_mulher_sem_conjuge": int(integrado["pct_sem_conjuge_resp_mulher_2022"].notna().sum()),
    }
    componentes = {
        "cwr_p75": int(integrado["F1_LOCAL_CWR_P75"].eq(1).sum()),
        "privacao_p75": int(integrado["F2"].eq(1).sum()),
        "entorno_f3_p75": int(integrado["F3"].eq(1).sum()),
        "resp_mulher_p75": int(integrado["F4_LOCAL_RESP_MULHER_P75"].eq(1).sum()),
    }
    convergencia = int(integrado["CONVERGENCIA_3_OU_4"].eq(1).sum())
    referencia_convergencia = int(qa_ref.get("setores_convergentes_p75", 1255))
    comp_cobertura = _comparar_contagens(cobertura, REFERENCIAS_COBERTURA)
    comp_componentes = _comparar_contagens(componentes, REFERENCIAS_COMPONENTES_P75)
    delta_convergencia = convergencia - referencia_convergencia
    setores_privacao_ausente = integrado.loc[integrado["PRIV_C3"].isna(), "codigo_setor"].astype(str).tolist()
    deriva = _tem_deriva(comp_cobertura) or _tem_deriva(comp_componentes) or delta_convergencia != 0
    status = "OK_COM_DERIVA_EDICAO" if deriva else "OK_REPRODUCAO_REFERENCIA"

    out_dir = paths.processed / "setorial"
    csv_path = out_dir / "base_familias_analiticas_p75.csv"
    parquet_path = out_dir / "base_familias_analiticas_p75.parquet"
    base.to_csv(csv_path, index=False, encoding="utf-8")
    base.to_parquet(parquet_path, index=False)
    registrar_arquivo(manifesto, csv_path, origem="Etapa 07 corrente - quatro famílias P75")
    registrar_arquivo(manifesto, parquet_path, origem="Etapa 07 corrente - quatro famílias P75")

    qa = {
        "status": status,
        "etapa": "07",
        "modo_execucao": "fontes_correntes_com_checkpoint_historico",
        "universo_base_setores": int(len(base)),
        "universo_integrado_checkpoint": esperado_integrado,
        "checkpoint_universo_integrado": checkpoint_meta,
        "percentil": q,
        "minimo_familias_convergencia": minimo,
        "fonte_arranjo": {"arquivo": arranjo_path.name, "url": arranjo_url},
        "limiares_correntes": limiares,
        "comparacao_limiares_historicos": _comparar_referencias(limiares, qa_ref.get("limiares_p75", {})),
        "cobertura_corrente": cobertura,
        "comparacao_cobertura_historica": comp_cobertura,
        "componentes_p75_correntes": componentes,
        "comparacao_componentes_historicos": comp_componentes,
        "convergencia_p75_corrente": convergencia,
        "convergencia_p75_referencia_historica": referencia_convergencia,
        "delta_convergencia_p75": delta_convergencia,
        "setores_checkpoint_sem_privacao_na_edicao_corrente": setores_privacao_ausente,
        "n_setores_checkpoint_sem_privacao_na_edicao_corrente": len(setores_privacao_ausente),
        "qa_f3_divergencias_com_06b": diverg_f3,
        "politica_deriva": (
            "O checkpoint histórico fixa apenas a identidade territorial. Valores temáticos são "
            "recalculados com a edição pública corrente; diferenças frente ao fechamento histórico "
            "são registradas como deriva de edição e não são corrigidas por truncamento ou imputação."
        ),
        "saidas": [str(csv_path.relative_to(paths.data_root)), str(parquet_path.relative_to(paths.data_root))],
    }
    qa_path = paths.qa / "etapa07_familias_analiticas_p75.json"
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    registrar_arquivo(manifesto, qa_path, origem="Etapa 07 corrente - QA P75")
    registrar_evento(manifesto, {
        "tipo": "etapa", "etapa": "07", "status": status,
        "modo": qa["modo_execucao"], "universo_integrado": esperado_integrado,
        "convergencia_p75_corrente": convergencia,
    })
    print(json.dumps(qa, ensure_ascii=False, indent=2))
