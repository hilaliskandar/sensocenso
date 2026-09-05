from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from .paths import resolve_paths
from .proveniencia import registrar_arquivo, registrar_evento


DOMINIOS = ["A", "E", "R", "D"]
REFERENCIA_LEGADA = {
    "n_c4": 6426,
    "pearson_A_E": 0.342,
    "pearson_A_R": 0.065,
    "pearson_A_D": 0.036,
    "pearson_E_R": 0.156,
    "pearson_E_D": 0.089,
    "pearson_R_D": 0.003,
    "pca_pc1_pct": 35.50,
    "alpha_padronizado": 0.34,
    "spearman_A_isau": 0.177,
    "spearman_E_isau": 0.300,
    "spearman_R_isau": 0.086,
    "spearman_D_isau": 0.947,
}


def _spearman(a: pd.Series, b: pd.Series) -> float:
    return float(a.rank(method="average").corr(b.rank(method="average"), method="pearson"))


def _alpha_padronizado(x: np.ndarray) -> float:
    z = pd.DataFrame(x, columns=DOMINIOS)
    k = len(DOMINIOS)
    variancia_itens = float(z.var(ddof=1).sum())
    variancia_soma = float(z.sum(axis=1).var(ddof=1))
    return float(k / (k - 1) * (1.0 - variancia_itens / variancia_soma))


def executar(raiz: Path) -> None:
    raiz = raiz.resolve()
    paths = resolve_paths(raiz)
    paths.create()
    manifesto = paths.manifests / "execucao.jsonl"

    base_path = paths.processed / "setorial" / "base_isau_2022.parquet"
    if not base_path.exists():
        raise FileNotFoundError(f"Base 05c ausente: {base_path}")
    base = pd.read_parquet(base_path)
    faltantes = [c for c in DOMINIOS + ["ISAU_C4", "ISAU_C3", "N_DOMINIOS_OBS", "DOMINIO_AUSENTE"] if c not in base.columns]
    if faltantes:
        raise ValueError(f"Base 05c sem colunas requeridas: {faltantes}")

    c4 = base.dropna(subset=DOMINIOS + ["ISAU_C4"]).copy()
    if c4.empty:
        raise AssertionError("Não há setores C4 para o Gate 05d.")

    pearson = c4[DOMINIOS].corr(method="pearson")
    spearman = c4[DOMINIOS].corr(method="spearman")
    x = StandardScaler().fit_transform(c4[DOMINIOS].astype(float))
    pca = PCA().fit(x)
    alpha = _alpha_padronizado(x)

    contribuicao = {}
    leave_one_out = {}
    for dominio in DOMINIOS:
        contribuicao[dominio] = _spearman(c4[dominio], c4["ISAU_C4"])
        outros = [c for c in DOMINIOS if c != dominio]
        alt = c4[outros].mean(axis=1)
        leave_one_out[dominio] = _spearman(c4["ISAU_C4"], alt)

    c3 = base.loc[base["ISAU_C3"].notna()].copy()
    incompletos = c3.loc[c3["N_DOMINIOS_OBS"] == 3].copy()
    padroes = incompletos["DOMINIO_AUSENTE"].fillna("").value_counts().to_dict()

    resumo_dominios = pd.DataFrame(
        {
            "dominio": DOMINIOS,
            "media_c4": [float(c4[c].mean()) for c in DOMINIOS],
            "desvio_padrao_c4": [float(c4[c].std(ddof=1)) for c in DOMINIOS],
            "spearman_com_isau_c4": [contribuicao[c] for c in DOMINIOS],
            "spearman_isau_leave_one_out": [leave_one_out[c] for c in DOMINIOS],
        }
    )

    qa_dir = paths.qa
    pearson_path = qa_dir / "etapa05d_correlacao_pearson_isau.csv"
    spearman_path = qa_dir / "etapa05d_correlacao_spearman_isau.csv"
    resumo_path = qa_dir / "etapa05d_resumo_dominios_isau.csv"
    pearson.to_csv(pearson_path, encoding="utf-8")
    spearman.to_csv(spearman_path, encoding="utf-8")
    resumo_dominios.to_csv(resumo_path, index=False, encoding="utf-8")
    for path in (pearson_path, spearman_path, resumo_path):
        registrar_arquivo(manifesto, path, origem="Gate 05d; base_isau_2022 corrigida")

    qa = {
        "status": "OK",
        "etapa": "05d",
        "objetivo": "reexecutar Gate 18G7C após correção da junção de drenagem por CD_SETOR",
        "n_c4": int(len(c4)),
        "n_c3": int(len(c3)),
        "n_c3_incompletos": int(len(incompletos)),
        "padroes_um_dominio_ausente": {str(k): int(v) for k, v in padroes.items()},
        "medias_c4": {c: float(c4[c].mean()) for c in DOMINIOS},
        "desvios_padrao_c4": {c: float(c4[c].std(ddof=1)) for c in DOMINIOS},
        "pearson": {a: {b: float(pearson.loc[a, b]) for b in DOMINIOS} for a in DOMINIOS},
        "spearman": {a: {b: float(spearman.loc[a, b]) for b in DOMINIOS} for a in DOMINIOS},
        "pca_variancia_explicada": [float(v) for v in pca.explained_variance_ratio_],
        "pca_componentes": {
            f"PC{i + 1}": {DOMINIOS[j]: float(pca.components_[i, j]) for j in range(len(DOMINIOS))}
            for i in range(len(DOMINIOS))
        },
        "alpha_padronizado": alpha,
        "spearman_dominio_isau_c4": contribuicao,
        "spearman_leave_one_out": leave_one_out,
        "deficit_medio_c4": float((1.0 - c4["ISAU_C4"]).mean()),
        "deficit_medio_c3_incompleto": float((1.0 - incompletos["ISAU_C3"]).mean()) if len(incompletos) else None,
        "referencia_legada_g7c": REFERENCIA_LEGADA,
        "nota_referencia_legada": (
            "A referência histórica é apenas comparativa para G7C porque a auditoria de reprodutibilidade "
            "identificou desalinhamento posicional nas colunas legadas de drenagem. Não deve ser usada como gate de igualdade."
        ),
        "saidas": [
            str(pearson_path.relative_to(paths.data_root)),
            str(spearman_path.relative_to(paths.data_root)),
            str(resumo_path.relative_to(paths.data_root)),
        ],
    }
    qa_path = qa_dir / "etapa05d_estrutura_dimensional_isau.json"
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    registrar_arquivo(manifesto, qa_path, origem="Gate 05d; reexecução corrigida do Gate 18G7C")
    registrar_evento(
        manifesto,
        {
            "tipo": "etapa",
            "etapa": "05d",
            "status": "OK",
            "n_c4": int(len(c4)),
            "n_c3": int(len(c3)),
            "saida": str(qa_path.relative_to(paths.data_root)),
        },
    )
    print(json.dumps(qa, ensure_ascii=False, indent=2))
