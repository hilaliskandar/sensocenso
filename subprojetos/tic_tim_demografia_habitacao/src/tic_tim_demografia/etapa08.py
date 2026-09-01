from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .config import carregar_parametros
from .etapa07 import _combinar_familias, _flag_limiar, _limiar, _ou_triestado
from .paths import resolve_paths
from .proveniencia import registrar_arquivo, registrar_evento


F3_VARIAVEIS = ("sem_bueiro", "sem_calcada", "sem_pavimentacao", "sem_iluminacao", "sem_arvores")


def _contexto_unico(base: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "codigo_ibge",
        "cres_dpo_2010_2022",
        "diverg_dpo_pop_2010_2022",
        "re_2022",
        "pct_unipessoais_2022",
    ]
    contexto = base[cols].drop_duplicates().copy()
    if len(contexto) != 30 or contexto["codigo_ibge"].nunique() != 30:
        raise AssertionError(
            "A sensibilidade deve calcular limiares municipais sobre 30 municípios únicos, "
            f"não sobre setores repetidos; linhas={len(contexto)}"
        )
    return contexto


def _vetor(linha: pd.Series, colunas: list[str]) -> str:
    ativos = [c for c in colunas if pd.notna(linha[c]) and int(linha[c]) == 1]
    return "+".join(ativos) if ativos else "nenhuma"


def _normalizar_vetor_p80(valor: str) -> str:
    return str(valor).replace("_P80", "")


def executar(raiz: Path) -> None:
    raiz = raiz.resolve()
    paths = resolve_paths(raiz)
    paths.create()
    manifesto = paths.manifests / "execucao.jsonl"
    parametros = carregar_parametros(raiz / "config/parametros.yml")
    q = float(parametros["territorializacao"]["percentil_sensibilidade"])
    minimo = int(parametros["territorializacao"]["minimo_familias_convergencia"])
    qa_ref = parametros.get("qa_referencia", {})
    esperado_integrado = int(qa_ref.get("setores_universo_final", 8073))

    entrada = paths.processed / "setorial" / "base_familias_analiticas_p75.parquet"
    if not entrada.exists():
        raise FileNotFoundError(f"Pré-requisito 08 ausente: {entrada}. Execute primeiro --etapa 07.")
    base = pd.read_parquet(entrada)
    if len(base) != 9087 or base["codigo_setor"].astype("string").duplicated().any():
        raise AssertionError("Etapa 08 exige a base P75 de 9.087 setores urbanos únicos.")
    if "FLAG_UNIVERSO_INTEGRADO" not in base.columns:
        raise AssertionError("Base P75 não contém o gate explícito do universo integrado.")
    if int(base["FLAG_UNIVERSO_INTEGRADO"].sum()) != esperado_integrado:
        raise AssertionError(
            "Universo integrado recebido pela etapa 08 divergiu: "
            f"{int(base['FLAG_UNIVERSO_INTEGRADO'].sum())} != {esperado_integrado}"
        )

    contexto = _contexto_unico(base)
    integrado = base.loc[base["FLAG_UNIVERSO_INTEGRADO"]].copy()
    limiares = {
        "crescimento_dpo": _limiar(contexto["cres_dpo_2010_2022"], q, "crescimento DPO P80"),
        "divergencia_dpo_pop": _limiar(
            contexto["diverg_dpo_pop_2010_2022"], q, "divergência DPO-população P80"
        ),
        "cwr": _limiar(integrado["cwr_0_4_por_1000_m1549"], q, "CWR P80"),
        "privacao": _limiar(integrado["PRIV_C3"], q, "privação P80"),
        "re_60_0_14": _limiar(contexto["re_2022"], q, "razão de envelhecimento P80"),
        "unipessoais": _limiar(contexto["pct_unipessoais_2022"], q, "unipessoais P80"),
        "resp_mulher_sem_conjuge": _limiar(
            integrado["pct_sem_conjuge_resp_mulher_2022"], q, "responsável mulher sem cônjuge P80"
        ),
        "sem_bueiro": _limiar(integrado["sem_bueiro"], q, "sem bueiro P80"),
        "sem_calcada": _limiar(integrado["sem_calcada"], q, "sem calçada P80"),
        "sem_pavimentacao": _limiar(integrado["sem_pavimentacao"], q, "sem pavimentação P80"),
        "sem_iluminacao": _limiar(integrado["sem_iluminacao"], q, "sem iluminação P80"),
        "sem_arvores": _limiar(integrado["sem_arvores"], q, "sem árvores P80"),
    }

    base["F1_CTX_CRES_DPO_P80"] = _flag_limiar(
        base["cres_dpo_2010_2022"], limiares["crescimento_dpo"]
    )
    base["F1_CTX_DIVERG_P80"] = _flag_limiar(
        base["diverg_dpo_pop_2010_2022"], limiares["divergencia_dpo_pop"]
    )
    base["F1_LOCAL_CWR_P80"] = _flag_limiar(base["cwr_0_4_por_1000_m1549"], limiares["cwr"])
    base["F1_P80"] = _ou_triestado(
        base[["F1_CTX_CRES_DPO_P80", "F1_CTX_DIVERG_P80", "F1_LOCAL_CWR_P80"]]
    )

    base["F2_LOCAL_PRIV_P80"] = _flag_limiar(base["PRIV_C3"], limiares["privacao"])
    base["F2_P80"] = base["F2_LOCAL_PRIV_P80"].astype("Int64")

    f3_flags: list[str] = []
    for var in F3_VARIAVEIS:
        nome = var.removeprefix("sem_").upper()
        coluna = f"F3_LOCAL_SEM_{nome}_P80"
        base[coluna] = _flag_limiar(base[var], limiares[var], zero_estrito=True)
        f3_flags.append(coluna)
    f3_tab = base[f3_flags]
    base["F3_N_COMPONENTES_OBS_P80"] = f3_tab.notna().sum(axis=1).astype("Int64")
    base["F3_N_COMPONENTES_ALTOS_P80"] = f3_tab.eq(1).sum(axis=1).astype("Int64")
    base["F3_P80"] = pd.Series(pd.NA, index=base.index, dtype="Int64")
    completos_f3 = base["F3_N_COMPONENTES_OBS_P80"].eq(5)
    base.loc[completos_f3, "F3_P80"] = (
        base.loc[completos_f3, "F3_N_COMPONENTES_ALTOS_P80"].ge(2).astype("int64")
    )

    base["F4_CTX_RE_P80"] = _flag_limiar(base["re_2022"], limiares["re_60_0_14"])
    base["F4_CTX_UNIP_P80"] = _flag_limiar(
        base["pct_unipessoais_2022"], limiares["unipessoais"]
    )
    base["F4_LOCAL_RESP_MULHER_P80"] = _flag_limiar(
        base["pct_sem_conjuge_resp_mulher_2022"], limiares["resp_mulher_sem_conjuge"]
    )
    base["F4_P80"] = _ou_triestado(
        base[["F4_CTX_RE_P80", "F4_CTX_UNIP_P80", "F4_LOCAL_RESP_MULHER_P80"]]
    )

    fam80_cols = ["F1_P80", "F2_P80", "F3_P80", "F4_P80"]
    comb80 = _combinar_familias(base[fam80_cols], minimo)
    base["N_FAMILIAS_SINAL_P80"] = comb80["N_FAMILIAS_SINAL"]
    base["N_FAMILIAS_OBSERVADAS_P80"] = comb80["N_FAMILIAS_OBSERVADAS"]
    base["CONVERGENCIA_3_OU_4_P80"] = comb80["CONVERGENCIA_3_OU_4"]
    base["VETOR_FAMILIAS_P80"] = base[fam80_cols].apply(lambda r: _vetor(r, fam80_cols), axis=1)

    base["PERSISTENTE_P75_P80"] = pd.Series(pd.NA, index=base.index, dtype="Int64")
    conhecidos = base["CONVERGENCIA_3_OU_4"].notna() & base["CONVERGENCIA_3_OU_4_P80"].notna()
    base.loc[conhecidos, "PERSISTENTE_P75_P80"] = (
        base.loc[conhecidos, "CONVERGENCIA_3_OU_4"].eq(1)
        & base.loc[conhecidos, "CONVERGENCIA_3_OU_4_P80"].eq(1)
    ).astype("int64")

    p75_cols = ["F1", "F2", "F3", "F4"]
    base["VETOR_FAMILIAS_P75"] = base[p75_cols].apply(lambda r: _vetor(r, p75_cols), axis=1)
    base["MESMO_VETOR_P75_P80"] = (
        base["VETOR_FAMILIAS_P75"]
        == base["VETOR_FAMILIAS_P80"].map(_normalizar_vetor_p80)
    ).astype("Int64")

    integrado = base.loc[base["FLAG_UNIVERSO_INTEGRADO"]].copy()
    converg_p75 = int(integrado["CONVERGENCIA_3_OU_4"].eq(1).sum())
    esperado_p75 = int(qa_ref.get("setores_convergentes_p75", 1255))
    if converg_p75 != esperado_p75:
        raise AssertionError(f"Gate P75 recebido pela etapa 08 divergiu: {converg_p75} != {esperado_p75}")

    persistentes = int(integrado["PERSISTENTE_P75_P80"].eq(1).sum())
    esperado_persistentes = int(qa_ref.get("setores_persistentes_p80", 959))
    if persistentes != esperado_persistentes:
        raise AssertionError(
            "Persistência P75/P80 no universo integrado divergiu: "
            f"{persistentes} != {esperado_persistentes}"
        )

    mesmo_vetor = int(
        (
            integrado["PERSISTENTE_P75_P80"].eq(1)
            & integrado["MESMO_VETOR_P75_P80"].eq(1)
        ).sum()
    )
    esperado_mesmo_vetor = int(qa_ref.get("setores_mesmo_vetor_p80", 886))
    if mesmo_vetor != esperado_mesmo_vetor:
        raise AssertionError(
            "Estabilidade do vetor P75/P80 no universo integrado divergiu: "
            f"{mesmo_vetor} != {esperado_mesmo_vetor}"
        )

    out_dir = paths.processed / "setorial"
    csv_path = out_dir / "base_familias_sensibilidade_p75_p80.csv"
    parquet_path = out_dir / "base_familias_sensibilidade_p75_p80.parquet"
    base.to_csv(csv_path, index=False, encoding="utf-8")
    base.to_parquet(parquet_path, index=False)
    registrar_arquivo(manifesto, csv_path, origem="Etapa 08 - sensibilidade P75/P80")
    registrar_arquivo(manifesto, parquet_path, origem="Etapa 08 - sensibilidade P75/P80")

    qa = {
        "status": "OK",
        "etapa": "08",
        "percentil_sensibilidade": q,
        "universo_base_setores": int(len(base)),
        "universo_integrado": int(base["FLAG_UNIVERSO_INTEGRADO"].sum()),
        "limiares_p80": limiares,
        "convergencia_p75_integrada": converg_p75,
        "convergencia_p80_integrada": int(integrado["CONVERGENCIA_3_OU_4_P80"].eq(1).sum()),
        "persistentes_p75_p80_integrados": persistentes,
        "mesmo_vetor_entre_persistentes": mesmo_vetor,
        "referencias_fechamento_8073": {
            "setores_convergentes_p75": esperado_p75,
            "setores_persistentes_p80": esperado_persistentes,
            "setores_mesmo_vetor_p80": esperado_mesmo_vetor,
        },
        "regra": (
            "percentis setoriais P80 calculados no mesmo universo integrado de 8.073 setores; "
            "variáveis municipais continuam calculadas sobre os 30 municípios únicos"
        ),
        "saidas": [
            str(csv_path.relative_to(paths.data_root)),
            str(parquet_path.relative_to(paths.data_root)),
        ],
    }
    qa_path = paths.qa / "etapa08_sensibilidade_p75_p80.json"
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    registrar_arquivo(manifesto, qa_path, origem="Etapa 08 - QA sensibilidade P75/P80")
    registrar_evento(
        manifesto,
        {
            "tipo": "etapa",
            "etapa": "08",
            "status": "OK",
            "universo_integrado": esperado_integrado,
            "persistentes": persistentes,
            "mesmo_vetor": mesmo_vetor,
        },
    )
    print(json.dumps(qa, ensure_ascii=False, indent=2))
