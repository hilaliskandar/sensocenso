"""Etapa 08 em modo de fontes públicas correntes.

A sensibilidade P80 é recalculada sobre o mesmo checkpoint territorial histórico
de 8.073 setores. As contagens 1.255/959/886 permanecem oráculos históricos de
QA e não bloqueiam a execução quando uma nova edição da fonte altera valores.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .config import carregar_parametros
from .etapa07 import _combinar_familias, _flag_limiar, _limiar, _ou_triestado
from .etapa08 import F3_VARIAVEIS, _contexto_unico, _normalizar_vetor_p80, _vetor
from .paths import resolve_paths
from .proveniencia import registrar_arquivo, registrar_evento


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
        raise AssertionError("Universo integrado territorial recebido pela etapa 08 não fecha em 8.073.")

    contexto = _contexto_unico(base)
    integrado = base.loc[base["FLAG_UNIVERSO_INTEGRADO"]].copy()
    limiares = {
        "crescimento_dpo": _limiar(contexto["cres_dpo_2010_2022"], q, "crescimento DPO P80"),
        "divergencia_dpo_pop": _limiar(contexto["diverg_dpo_pop_2010_2022"], q, "divergência DPO-população P80"),
        "cwr": _limiar(integrado["cwr_0_4_por_1000_m1549"], q, "CWR P80"),
        "privacao": _limiar(integrado["PRIV_C3"], q, "privação P80"),
        "re_60_0_14": _limiar(contexto["re_2022"], q, "razão de envelhecimento P80"),
        "unipessoais": _limiar(contexto["pct_unipessoais_2022"], q, "unipessoais P80"),
        "resp_mulher_sem_conjuge": _limiar(integrado["pct_sem_conjuge_resp_mulher_2022"], q, "responsável mulher sem cônjuge P80"),
        **{var: _limiar(integrado[var], q, f"{var} P80") for var in F3_VARIAVEIS},
    }

    base["F1_CTX_CRES_DPO_P80"] = _flag_limiar(base["cres_dpo_2010_2022"], limiares["crescimento_dpo"])
    base["F1_CTX_DIVERG_P80"] = _flag_limiar(base["diverg_dpo_pop_2010_2022"], limiares["divergencia_dpo_pop"])
    base["F1_LOCAL_CWR_P80"] = _flag_limiar(base["cwr_0_4_por_1000_m1549"], limiares["cwr"])
    base["F1_P80"] = _ou_triestado(base[["F1_CTX_CRES_DPO_P80", "F1_CTX_DIVERG_P80", "F1_LOCAL_CWR_P80"]])

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
    base.loc[completos_f3, "F3_P80"] = base.loc[completos_f3, "F3_N_COMPONENTES_ALTOS_P80"].ge(2).astype("int64")

    base["F4_CTX_RE_P80"] = _flag_limiar(base["re_2022"], limiares["re_60_0_14"])
    base["F4_CTX_UNIP_P80"] = _flag_limiar(base["pct_unipessoais_2022"], limiares["unipessoais"])
    base["F4_LOCAL_RESP_MULHER_P80"] = _flag_limiar(base["pct_sem_conjuge_resp_mulher_2022"], limiares["resp_mulher_sem_conjuge"])
    base["F4_P80"] = _ou_triestado(base[["F4_CTX_RE_P80", "F4_CTX_UNIP_P80", "F4_LOCAL_RESP_MULHER_P80"]])

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
        base["VETOR_FAMILIAS_P75"] == base["VETOR_FAMILIAS_P80"].map(_normalizar_vetor_p80)
    ).astype("Int64")

    integrado = base.loc[base["FLAG_UNIVERSO_INTEGRADO"]].copy()
    observado = {
        "convergencia_p75": int(integrado["CONVERGENCIA_3_OU_4"].eq(1).sum()),
        "convergencia_p80": int(integrado["CONVERGENCIA_3_OU_4_P80"].eq(1).sum()),
        "persistentes_p75_p80": int(integrado["PERSISTENTE_P75_P80"].eq(1).sum()),
        "mesmo_vetor_entre_persistentes": int((integrado["PERSISTENTE_P75_P80"].eq(1) & integrado["MESMO_VETOR_P75_P80"].eq(1)).sum()),
    }
    referencia = {
        "convergencia_p75": int(qa_ref.get("setores_convergentes_p75", 1255)),
        "persistentes_p75_p80": int(qa_ref.get("setores_persistentes_p80", 959)),
        "mesmo_vetor_entre_persistentes": int(qa_ref.get("setores_mesmo_vetor_p80", 886)),
    }
    comparacao = {
        chave: {
            "observado_corrente": observado[chave],
            "referencia_historica": valor,
            "delta": observado[chave] - valor,
        }
        for chave, valor in referencia.items()
    }
    deriva = any(v["delta"] != 0 for v in comparacao.values())
    status = "OK_COM_DERIVA_EDICAO" if deriva else "OK_REPRODUCAO_REFERENCIA"

    out_dir = paths.processed / "setorial"
    csv_path = out_dir / "base_familias_sensibilidade_p75_p80.csv"
    parquet_path = out_dir / "base_familias_sensibilidade_p75_p80.parquet"
    base.to_csv(csv_path, index=False, encoding="utf-8")
    base.to_parquet(parquet_path, index=False)
    registrar_arquivo(manifesto, csv_path, origem="Etapa 08 corrente - sensibilidade P75/P80")
    registrar_arquivo(manifesto, parquet_path, origem="Etapa 08 corrente - sensibilidade P75/P80")

    qa = {
        "status": status,
        "etapa": "08",
        "modo_execucao": "fontes_correntes_com_checkpoint_historico",
        "percentil_sensibilidade": q,
        "universo_base_setores": int(len(base)),
        "universo_integrado_checkpoint": int(base["FLAG_UNIVERSO_INTEGRADO"].sum()),
        "limiares_p80_correntes": limiares,
        "observado_corrente": observado,
        "comparacao_referencias_historicas": comparacao,
        "politica_deriva": (
            "Persistência e estabilidade são recalculadas com valores correntes dentro do mesmo universo histórico. "
            "Os números 1.255/959/886 permanecem referências de regressão do fechamento, não metas a forçar."
        ),
        "saidas": [str(csv_path.relative_to(paths.data_root)), str(parquet_path.relative_to(paths.data_root))],
    }
    qa_path = paths.qa / "etapa08_sensibilidade_p75_p80.json"
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    registrar_arquivo(manifesto, qa_path, origem="Etapa 08 corrente - QA sensibilidade")
    registrar_evento(manifesto, {
        "tipo": "etapa", "etapa": "08", "status": status, "modo": qa["modo_execucao"],
        "universo_integrado": esperado_integrado,
        "persistentes_correntes": observado["persistentes_p75_p80"],
        "mesmo_vetor_corrente": observado["mesmo_vetor_entre_persistentes"],
    })
    print(json.dumps(qa, ensure_ascii=False, indent=2))
