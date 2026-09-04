"""Etapa 10b corrente: camadas distributivas de raça/cor, FCU e arranjo doméstico.

Reconstrói as camadas ex post usadas no diagnóstico regional sem alterar as
quatro famílias analíticas, a gravidade físico-urbana, o checkpoint territorial
ou qualquer regra de priorização. A etapa é uma subdivisão operacional do
pipeline para tornar explícita a integração distributiva prevista antes da
geração automática de tabelas e mapas.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
from scipy.stats import spearmanr

from .etapa05c import _coluna, _ler_csv_zip, _numero, _preparar_setor
from .fontes.http import HttpClient, listar_links_indice
from .paths import resolve_paths
from .proveniencia import registrar_arquivo, registrar_evento


RACA_VARIAVEIS = {
    "branca": "V01317",
    "preta": "V01318",
    "amarela": "V01319",
    "parda": "V01320",
    "indigena": "V01321",
}
REFERENCIAS_HISTORICAS = {
    "pct_preta_parda_30m": 0.3974507745638293,
    "pct_pop_fcu_30m": 0.05530782351459498,
    "cobertura_parentesco": 0.9593925387916804,
    "setores_parentesco_validos": 8718,
    "spearman_preta_parda_gravidade": 0.7569251353991385,
    "spearman_fcu_gravidade": 0.347504740883375,
    "spearman_arranjo_gravidade": -0.5860496198240245,
}


def _carregar_json(path: Path) -> dict:
    dados = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(dados, dict):
        raise ValueError(f"JSON estrutural inválido: {path}")
    return dados


def _nome_url(url: str) -> str:
    return Path(urlparse(url).path).name


def _selecionar_unico(links: list[str], *, token: str, sufixo: str) -> str:
    candidatos = [
        str(url)
        for url in links
        if token.casefold() in _nome_url(str(url)).casefold()
        and _nome_url(str(url)).casefold().endswith(sufixo.casefold())
    ]
    if len(candidatos) != 1:
        raise ValueError(
            f"Fonte não resolvida unicamente para token={token}, sufixo={sufixo}: {candidatos}"
        )
    return candidatos[0]


def _baixar_se_ausente(cliente: HttpClient, url: str, destino: Path, manifesto: Path) -> Path:
    if destino.exists():
        return destino
    return cliente.baixar_arquivo(url, destino, manifesto=manifesto)


def _normalizar_nome(valor: object) -> str:
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", texto.casefold())


def _coluna_alias(df: pd.DataFrame, aliases: tuple[str, ...], *, obrigatoria: bool = True) -> str | None:
    mapa = {_normalizar_nome(c): str(c) for c in df.columns}
    for alias in aliases:
        achou = mapa.get(_normalizar_nome(alias))
        if achou is not None:
            return achou
    if obrigatoria:
        raise ValueError(f"Coluna não encontrada. Alternativas={aliases}; colunas={list(df.columns)[:40]}")
    return None


def _setores_fcu_xlsx(path: Path, setores_urbanos: pd.Index) -> tuple[set[str], dict]:
    permitidos = {str(x) for x in setores_urbanos}
    workbook = pd.ExcelFile(path)
    candidatos: list[tuple[str, pd.DataFrame, str, str | None]] = []
    for planilha in workbook.sheet_names:
        df = pd.read_excel(workbook, sheet_name=planilha, dtype="string")
        if df.empty:
            continue
        setor_col = _coluna_alias(
            df,
            ("CD_SETOR", "codigo_setor", "código do setor", "cod_setor"),
            obrigatoria=False,
        )
        if setor_col is None:
            continue
        fcu_col = _coluna_alias(
            df,
            ("CD_FCU", "codigo_fcu", "código da fcu", "cod_fcu"),
            obrigatoria=False,
        )
        candidatos.append((planilha, df, setor_col, fcu_col))
    if len(candidatos) != 1:
        raise ValueError(
            "Arquivo FCU deve conter exatamente uma planilha com código setorial; "
            f"candidatas={[x[0] for x in candidatos]}"
        )

    planilha, df, setor_col, fcu_col = candidatos[0]
    cod = (
        df[setor_col]
        .astype("string")
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
    )
    if fcu_col is None:
        efetivo = cod.notna() & cod.ne("")
        modo = "linhas_da_tabela_oficial_de_setores_fcu"
        n_fcu = None
    else:
        marcador = df[fcu_col].astype("string").str.strip()
        efetivo = cod.notna() & cod.ne("") & marcador.notna() & marcador.ne("") & marcador.ne(".")
        modo = "cd_fcu_efetivo; ponto_explicito_como_nao_fcu"
        n_fcu = int(marcador.loc[efetivo].nunique())

    selecionados = set(cod.loc[efetivo].astype(str)) & permitidos
    if not selecionados:
        raise ValueError("Nenhum setor FCU do arquivo oficial intersecta o universo urbano corrente.")
    meta = {
        "planilha": planilha,
        "coluna_setor": setor_col,
        "coluna_fcu": fcu_col,
        "modo_marcacao": modo,
        "linhas_tabela": int(len(df)),
        "setores_fcu_no_universo_30m": int(len(selecionados)),
        "n_fcu_distintas": n_fcu,
    }
    return selecionados, meta


def _agregar_raca(
    fonte: pd.DataFrame,
    indice: pd.Index,
    codigo_ibge_por_setor: pd.Series,
) -> pd.DataFrame:
    fonte = fonte.reindex(indice)
    tab = pd.DataFrame(index=indice)
    for nome, var in RACA_VARIAVEIS.items():
        tab[nome] = _numero(fonte[_coluna(fonte, var)], var)
    tab["codigo_ibge"] = codigo_ibge_por_setor.reindex(indice).astype("string")
    somas = tab.groupby("codigo_ibge", sort=True)[list(RACA_VARIAVEIS)].sum(min_count=1)
    somas["raca_valida_urbana"] = somas[list(RACA_VARIAVEIS)].sum(axis=1, min_count=1)
    somas["preta_parda"] = somas["preta"] + somas["parda"]
    for nome in RACA_VARIAVEIS:
        somas[f"pct_{nome}_urbano"] = (
            somas[nome] / somas["raca_valida_urbana"]
        ).where(somas["raca_valida_urbana"].gt(0))
    somas["pct_preta_parda_urbano"] = (
        somas["preta_parda"] / somas["raca_valida_urbana"]
    ).where(somas["raca_valida_urbana"].gt(0))
    return somas


def _agregar_arranjo(familias: pd.DataFrame) -> pd.DataFrame:
    base = familias.copy()
    base["codigo_ibge"] = base["codigo_ibge"].astype("string")
    den = pd.to_numeric(base["v01179_domicilios_sem_conjuge"], errors="coerce")
    num = pd.to_numeric(base["v01188_resp_mulher_sem_conjuge"], errors="coerce")
    valido = den.notna() & num.notna() & den.gt(0) & num.le(den)
    base["den_valido"] = den.where(valido)
    base["num_valido"] = num.where(valido)
    base["par_valido"] = valido.astype("int64")
    agg = base.groupby("codigo_ibge", sort=True).agg(
        dom_sem_conjuge_pub_urbano=("den_valido", "sum"),
        dom_sem_conjuge_resp_mulher_pub_urbano=("num_valido", "sum"),
        setores_validos_parentesco=("par_valido", "sum"),
        setores_urbanos_parentesco=("codigo_setor", "size"),
    )
    agg["pct_dom_sem_conjuge_resp_mulher_urbano"] = (
        agg["dom_sem_conjuge_resp_mulher_pub_urbano"] / agg["dom_sem_conjuge_pub_urbano"]
    ).where(agg["dom_sem_conjuge_pub_urbano"].gt(0))
    agg["cobertura_setorial_parentesco"] = (
        agg["setores_validos_parentesco"] / agg["setores_urbanos_parentesco"]
    )
    return agg


def _agregar_fcu(base_urbana: pd.DataFrame, setores_fcu: set[str]) -> pd.DataFrame:
    base = base_urbana.copy()
    base["codigo_setor"] = base["codigo_setor"].astype("string").str.strip()
    base["codigo_ibge"] = base["codigo_ibge"].astype("string")
    base["POP_TOTAL"] = pd.to_numeric(base["POP_TOTAL"], errors="coerce")
    base["DPPO"] = pd.to_numeric(base["DPPO"], errors="coerce")
    base["FLAG_FCU"] = base["codigo_setor"].astype(str).isin(setores_fcu)
    base["pop_fcu"] = base["POP_TOTAL"].where(base["FLAG_FCU"], 0)
    base["dppo_fcu"] = base["DPPO"].where(base["FLAG_FCU"], 0)
    base["setor_fcu"] = base["FLAG_FCU"].astype("int64")
    agg = base.groupby("codigo_ibge", sort=True).agg(
        pop_urbana_malha=("POP_TOTAL", "sum"),
        dpo_urbanos_malha=("DPPO", "sum"),
        setores_urbanos=("codigo_setor", "size"),
        setores_fcu=("setor_fcu", "sum"),
        pop_fcu_urbana=("pop_fcu", "sum"),
        dpo_fcu_urbanos=("dppo_fcu", "sum"),
    )
    agg["pct_pop_urbana_em_fcu"] = (
        agg["pop_fcu_urbana"] / agg["pop_urbana_malha"]
    ).where(agg["pop_urbana_malha"].gt(0))
    agg["pct_dpo_urbanos_em_fcu"] = (
        agg["dpo_fcu_urbanos"] / agg["dpo_urbanos_malha"]
    ).where(agg["dpo_urbanos_malha"].gt(0))
    agg["pct_setores_urbanos_fcu"] = agg["setores_fcu"] / agg["setores_urbanos"]
    return agg


def _rr(serie: pd.Series, referencia: float) -> pd.Series:
    if referencia <= 0:
        raise ValueError("Referência regional de RR deve ser positiva.")
    return pd.to_numeric(serie, errors="coerce") / float(referencia)


def _flag_rr(valor: float) -> str | None:
    if pd.isna(valor):
        return None
    if valor >= 1.10:
        return ">=10% acima da referência"
    if valor <= 0.90:
        return ">=10% abaixo da referência"
    return "próximo da referência"


def _flag_fcu(valor: float) -> str | None:
    if pd.isna(valor):
        return None
    if valor <= 0:
        return "Sem população FCU identificada"
    if valor >= 0.10:
        return "FCU >=10% pop urbana"
    return "FCU <10% pop urbana"


def _spearman(x: pd.Series, y: pd.Series) -> dict[str, float | int]:
    tab = pd.concat([pd.to_numeric(x, errors="coerce"), pd.to_numeric(y, errors="coerce")], axis=1).dropna()
    if len(tab) < 3:
        raise ValueError("Spearman exige ao menos três pares válidos.")
    rho, p = spearmanr(tab.iloc[:, 0].to_numpy(), tab.iloc[:, 1].to_numpy())
    return {"n": int(len(tab)), "rho": float(rho), "p_valor": float(p)}


def executar(raiz: Path) -> None:
    raiz = raiz.resolve()
    paths = resolve_paths(raiz)
    paths.create()
    manifesto = paths.manifests / "execucao.jsonl"

    arquivos = {
        "urbana": paths.processed / "setorial" / "base_isau_priorizacao_2022.parquet",
        "familias": paths.processed / "setorial" / "base_familias_analiticas_p75.parquet",
        "sintese": paths.processed / "municipal" / "base_sintese_municipal_2022.parquet",
        "indice_agregados": paths.raw / "ibge" / "indices_publicacao" / "censo2022_agregados_setor.json",
        "indice_fcu": paths.raw / "ibge" / "indices_publicacao" / "censo2022_fcu.json",
    }
    for nome, path in arquivos.items():
        if not path.exists():
            raise FileNotFoundError(f"Pré-requisito 10b ausente ({nome}): {path}")

    urbana = pd.read_parquet(arquivos["urbana"])
    familias = pd.read_parquet(arquivos["familias"])
    sintese = pd.read_parquet(arquivos["sintese"])
    urbana["codigo_setor"] = urbana["codigo_setor"].astype("string").str.strip()
    urbana["codigo_ibge"] = urbana["codigo_ibge"].astype("string").str.strip()
    if len(urbana) != 9087 or urbana["codigo_setor"].duplicated().any():
        raise AssertionError("Etapa 10b exige o universo urbano corrente de 9.087 setores únicos.")
    indice = pd.Index(urbana["codigo_setor"], name="codigo_setor")
    codigo_ibge_por_setor = urbana.set_index("codigo_setor")["codigo_ibge"].reindex(indice)
    municipios = urbana[["codigo_ibge", "municipio"]].drop_duplicates().sort_values("codigo_ibge")
    if len(municipios) != 30:
        raise AssertionError(f"Etapa 10b exige 30 municípios; obtidos={len(municipios)}")

    cliente = HttpClient(timeout=600)
    raw_dist = paths.raw / "ibge" / "censo2022" / "distributivas"
    raw_raca = raw_dist / "raca"
    raw_fcu = raw_dist / "fcu"
    raw_raca.mkdir(parents=True, exist_ok=True)
    raw_fcu.mkdir(parents=True, exist_ok=True)

    snap_agreg = _carregar_json(arquivos["indice_agregados"])
    url_raca = _selecionar_unico(
        [str(x) for x in snap_agreg.get("links", [])], token="cor_ou_raca", sufixo=".zip"
    )
    path_raca = _baixar_se_ausente(cliente, url_raca, raw_raca / _nome_url(url_raca), manifesto)
    fonte_raca = _preparar_setor(_ler_csv_zip(path_raca), "CD_setor", "CD_SETOR", "setor")
    raca = _agregar_raca(fonte_raca, indice, codigo_ibge_por_setor)

    snap_fcu = _carregar_json(arquivos["indice_fcu"])
    anexos = [str(x) for x in snap_fcu.get("links", []) if str(x).rstrip("/").casefold().endswith("/anexos")]
    if len(anexos) != 1:
        raise ValueError(f"Diretório Anexos da publicação FCU não resolvido unicamente: {anexos}")
    links_anexos = listar_links_indice(anexos[0], cliente=cliente)
    snapshot_anexos = paths.raw / "ibge" / "indices_publicacao" / "censo2022_fcu_anexos.json"
    if not snapshot_anexos.exists():
        snapshot_anexos.write_text(
            json.dumps({"url": anexos[0], "links": links_anexos}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        registrar_arquivo(manifesto, snapshot_anexos, origem=anexos[0])
    url_fcu = _selecionar_unico(links_anexos, token="setores", sufixo=".xlsx")
    path_fcu = _baixar_se_ausente(cliente, url_fcu, raw_fcu / _nome_url(url_fcu), manifesto)
    setores_fcu, fcu_meta = _setores_fcu_xlsx(path_fcu, indice)
    fcu = _agregar_fcu(urbana, setores_fcu)
    arranjo = _agregar_arranjo(familias)

    base = municipios.set_index("codigo_ibge").join(raca, how="left").join(fcu, how="left").join(arranjo, how="left")
    if base.isna().all(axis=1).any():
        raise AssertionError("Há município sem qualquer informação distributiva após integração.")

    ref_raca_corrente = float(base["preta_parda"].sum() / base["raca_valida_urbana"].sum())
    ref_fcu_corrente = float(base["pop_fcu_urbana"].sum() / base["pop_urbana_malha"].sum())
    ref_arranjo_corrente = float(
        base["dom_sem_conjuge_resp_mulher_pub_urbano"].sum()
        / base["dom_sem_conjuge_pub_urbano"].sum()
    )
    base["rr_mun_preta_parda"] = _rr(base["pct_preta_parda_urbano"], ref_raca_corrente)
    base["rr_mun_fcu"] = _rr(base["pct_pop_urbana_em_fcu"], ref_fcu_corrente)
    base["rr_mun_sem_conjuge_resp_mulher"] = _rr(
        base["pct_dom_sem_conjuge_resp_mulher_urbano"], ref_arranjo_corrente
    )
    base["flag_sobrerrep_preta_parda"] = base["rr_mun_preta_parda"].map(_flag_rr)
    base["flag_fcu"] = base["pct_pop_urbana_em_fcu"].map(_flag_fcu)
    base["flag_sobrerrep_sem_conjuge_resp_mulher"] = base["rr_mun_sem_conjuge_resp_mulher"].map(_flag_rr)

    sintese["codigo_ibge"] = sintese["codigo_ibge"].astype("string")
    grav = sintese.set_index("codigo_ibge")["gravidade_fisico_urbana"].reindex(base.index)
    correlacoes = {
        "preta_parda_vs_gravidade": _spearman(base["pct_preta_parda_urbano"], grav),
        "fcu_vs_gravidade": _spearman(base["pct_pop_urbana_em_fcu"], grav),
        "arranjo_vs_gravidade": _spearman(base["pct_dom_sem_conjuge_resp_mulher_urbano"], grav),
    }
    referencias_corr = {
        "preta_parda_vs_gravidade": REFERENCIAS_HISTORICAS["spearman_preta_parda_gravidade"],
        "fcu_vs_gravidade": REFERENCIAS_HISTORICAS["spearman_fcu_gravidade"],
        "arranjo_vs_gravidade": REFERENCIAS_HISTORICAS["spearman_arranjo_gravidade"],
    }
    for nome, valor in correlacoes.items():
        valor["rho_referencia_historica"] = float(referencias_corr[nome])
        valor["delta_rho"] = float(valor["rho"] - referencias_corr[nome])

    cobertura_global = float(base["setores_validos_parentesco"].sum() / base["setores_urbanos_parentesco"].sum())
    n_validos_parentesco = int(base["setores_validos_parentesco"].sum())
    status = "OK_COM_DERIVA_EDICAO"
    if (
        abs(ref_raca_corrente - REFERENCIAS_HISTORICAS["pct_preta_parda_30m"]) < 1e-12
        and abs(ref_fcu_corrente - REFERENCIAS_HISTORICAS["pct_pop_fcu_30m"]) < 1e-12
        and abs(cobertura_global - REFERENCIAS_HISTORICAS["cobertura_parentesco"]) < 1e-12
    ):
        status = "OK_REPRODUCAO_REFERENCIA"

    out = base.reset_index()
    out_dir = paths.processed / "municipal"
    csv_path = out_dir / "base_camadas_distributivas_2022.csv"
    parquet_path = out_dir / "base_camadas_distributivas_2022.parquet"
    out.to_csv(csv_path, index=False, encoding="utf-8")
    out.to_parquet(parquet_path, index=False)
    registrar_arquivo(manifesto, csv_path, origem="Etapa 10b corrente — camadas distributivas")
    registrar_arquivo(manifesto, parquet_path, origem="Etapa 10b corrente — camadas distributivas")

    corr_path = paths.qa / "etapa10b_correlacoes_distributivas.csv"
    pd.DataFrame([{"par": k, **v} for k, v in correlacoes.items()]).to_csv(corr_path, index=False, encoding="utf-8")
    registrar_arquivo(manifesto, corr_path, origem="Etapa 10b corrente — correlações distributivas")

    qa = {
        "status": status,
        "etapa": "10b",
        "modo_execucao": "fontes_correntes; caracterizacao_ex_post",
        "regra_analitica": (
            "raça/cor, FCU e arranjo doméstico são camadas distributivas ex post; "
            "não alteram F1–F4, gravidade físico-urbana, clusters ou prioridade"
        ),
        "universo_urbano_setores": int(len(urbana)),
        "municipios": int(len(base)),
        "fontes": {
            "raca": {"url": url_raca, "arquivo": path_raca.name, "variaveis": RACA_VARIAVEIS},
            "fcu": {"url": url_fcu, "arquivo": path_fcu.name, **fcu_meta},
            "arranjo": {
                "origem": "base_familias_analiticas_p75 produzida pela etapa 07",
                "denominador": "V01179",
                "numerador": "V01188",
            },
        },
        "referencias_regionais_correntes": {
            "pct_preta_parda_30m": ref_raca_corrente,
            "pct_pop_fcu_30m": ref_fcu_corrente,
            "pct_sem_conjuge_resp_mulher_30m": ref_arranjo_corrente,
            "setores_parentesco_validos": n_validos_parentesco,
            "cobertura_parentesco": cobertura_global,
        },
        "comparacao_historica": {
            "pct_preta_parda_30m": {
                "corrente": ref_raca_corrente,
                "historica": REFERENCIAS_HISTORICAS["pct_preta_parda_30m"],
                "delta": ref_raca_corrente - REFERENCIAS_HISTORICAS["pct_preta_parda_30m"],
            },
            "pct_pop_fcu_30m": {
                "corrente": ref_fcu_corrente,
                "historica": REFERENCIAS_HISTORICAS["pct_pop_fcu_30m"],
                "delta": ref_fcu_corrente - REFERENCIAS_HISTORICAS["pct_pop_fcu_30m"],
            },
            "setores_parentesco_validos": {
                "corrente": n_validos_parentesco,
                "historica": REFERENCIAS_HISTORICAS["setores_parentesco_validos"],
                "delta": n_validos_parentesco - REFERENCIAS_HISTORICAS["setores_parentesco_validos"],
            },
            "cobertura_parentesco": {
                "corrente": cobertura_global,
                "historica": REFERENCIAS_HISTORICAS["cobertura_parentesco"],
                "delta": cobertura_global - REFERENCIAS_HISTORICAS["cobertura_parentesco"],
            },
        },
        "correlacoes_spearman": correlacoes,
    }
    qa_path = paths.qa / "etapa10b_camadas_distributivas.json"
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    registrar_arquivo(manifesto, qa_path, origem="Etapa 10b corrente — QA distributivo")
    registrar_evento(
        manifesto,
        {
            "tipo": "etapa",
            "etapa": "10b",
            "status": status,
            "municipios": int(len(base)),
            "setores_urbanos": int(len(urbana)),
            "pct_preta_parda_30m": ref_raca_corrente,
            "pct_pop_fcu_30m": ref_fcu_corrente,
            "cobertura_parentesco": cobertura_global,
        },
    )
    print(json.dumps(qa, ensure_ascii=False, indent=2))
