from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import pandas as pd

from .config import carregar_municipios
from .paths import resolve_paths
from .proveniencia import registrar_arquivo, registrar_evento


SIMBOLOS_SIGILO = {"x"}
A_VARS = ["V00464", "V00200", "V00201"]
E_VARS = ["V00312", "V00313", "V00314", "V00315", "V00316"]
R_VARS = ["V00399", "V00400", "V00401", "V00402"]
REFERENCIA_CADERNO = {
    "universo": 9087,
    "A_validos": 8492,
    "E_validos": 7156,
    "R_validos": 8259,
    "D_validos": 8486,
    "C4_validos": 6426,
    "C3_validos": 8291,
}


def _carregar_json(path: Path) -> dict:
    dados = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(dados, dict):
        raise ValueError(f"JSON estrutural invalido: {path}")
    return dados


def _detectar_encoding(bruto: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin1"):
        try:
            bruto.decode(encoding, errors="strict")
            return encoding
        except UnicodeDecodeError:
            continue
    raise ValueError("Codificacao CSV nao reconhecida.")


def _detectar_separador(bruto: bytes, encoding: str) -> str:
    primeira = bruto[:65536].decode(encoding, errors="strict").splitlines()[0]
    contagens = {";": primeira.count(";"), ",": primeira.count(","), "\t": primeira.count("\t")}
    sep, n = max(contagens.items(), key=lambda item: item[1])
    if n == 0:
        raise ValueError("Separador CSV nao reconhecido.")
    return sep


def _ler_csv_zip(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as zf:
        csvs = [m for m in zf.namelist() if m.casefold().endswith(".csv")]
        if len(csvs) != 1:
            raise ValueError(f"ZIP deve conter exatamente um CSV: {path}; encontrados={csvs}")
        bruto = zf.read(csvs[0])
    encoding = _detectar_encoding(bruto)
    sep = _detectar_separador(bruto, encoding)
    return pd.read_csv(io.BytesIO(bruto), sep=sep, dtype="string", encoding=encoding)


def _coluna(df: pd.DataFrame, *alternativas: str) -> str:
    mapa = {str(c).strip().casefold(): str(c) for c in df.columns}
    for alt in alternativas:
        achou = mapa.get(str(alt).strip().casefold())
        if achou is not None:
            return achou
    raise ValueError(f"Nenhuma das colunas esperadas foi encontrada: {alternativas}")


def _numero(serie: pd.Series, nome: str) -> pd.Series:
    bruto = serie.astype("string").str.strip()
    normalizado = bruto.str.replace(",", ".", regex=False)
    num = pd.to_numeric(normalizado, errors="coerce")
    mask = num.isna() & bruto.notna()
    inesperados = sorted(
        {
            str(x)
            for x in bruto.loc[mask].dropna().tolist()
            if str(x).casefold() not in SIMBOLOS_SIGILO
        }
    )
    if inesperados:
        raise ValueError(f"Valores nao numericos inesperados em {nome}: {inesperados}")
    return num.astype("float64")


def _proporcao(numerador: pd.Series, denominador: pd.Series) -> pd.Series:
    out = numerador / denominador
    out = out.where(denominador > 0)
    return out


def _validar_01(serie: pd.Series, nome: str, tolerancia: float = 1e-9) -> None:
    validos = serie.dropna()
    ruins = validos.loc[(validos < -tolerancia) | (validos > 1.0 + tolerancia)]
    if not ruins.empty:
        raise ValueError(
            f"{nome} fora de [0,1]: n={len(ruins)}; min={ruins.min()}; max={ruins.max()}"
        )


def calcular_a(df: pd.DataFrame) -> pd.DataFrame:
    den = _numero(df[_coluna(df, "V00001")], "V00001")
    props = []
    nomes = ["agua_fora_rede", "agua_so_terreno", "agua_nao_encanada"]
    for var, nome in zip(A_VARS, nomes, strict=True):
        p = _proporcao(_numero(df[_coluna(df, var)], var), den)
        _validar_01(p, nome)
        props.append(p.rename(nome))
    comp = pd.concat(props, axis=1)
    n = comp.notna().sum(axis=1)
    a = 1.0 - comp.mean(axis=1, skipna=True)
    a = a.where(n >= 2)
    _validar_01(a, "A")
    return pd.concat([comp, n.rename("A_n_medidas"), a.rename("A")], axis=1)


def calcular_e(df: pd.DataFrame) -> pd.DataFrame:
    den = _numero(df[_coluna(df, "V00001")], "V00001")
    nums = pd.concat(
        [_numero(df[_coluna(df, var)], var).rename(var) for var in E_VARS], axis=1
    )
    completo = nums.notna().all(axis=1) & den.notna() & (den > 0)
    prec = _proporcao(nums.sum(axis=1, min_count=len(E_VARS)), den).where(completo)
    _validar_01(prec, "esgoto_precario")
    e = (1.0 - prec).rename("E")
    _validar_01(e, "E")
    return pd.concat([prec.rename("esgoto_precario"), e], axis=1)


def calcular_r(df: pd.DataFrame) -> pd.DataFrame:
    den = _numero(df[_coluna(df, "V00001")], "V00001")
    nums = pd.concat(
        [_numero(df[_coluna(df, var)], var).rename(var) for var in R_VARS], axis=1
    )
    completo = nums.notna().all(axis=1) & den.notna() & (den > 0)
    inadequado = _proporcao(nums.sum(axis=1, min_count=len(R_VARS)), den).where(completo)
    _validar_01(inadequado, "lixo_inadequado")
    r = (1.0 - inadequado).rename("R")
    _validar_01(r, "R")
    return pd.concat([inadequado.rename("lixo_inadequado"), r], axis=1)


def calcular_sem_bueiro(
    df: pd.DataFrame, *, sim: str, nao: str, nao_declarado: str, prefixo: str
) -> pd.DataFrame:
    s = _numero(df[_coluna(df, sim)], sim)
    n = _numero(df[_coluna(df, nao)], nao)
    nd = _numero(df[_coluna(df, nao_declarado)], nao_declarado)
    den_valido = s + n
    sem = _proporcao(n, den_valido)
    _validar_01(sem, f"{prefixo}_sem_bueiro")
    return pd.DataFrame(
        {
            f"{prefixo}_bueiro_sim": s,
            f"{prefixo}_bueiro_nao": n,
            f"{prefixo}_bueiro_nao_declarado": nd,
            f"{prefixo}_bueiro_denominador_valido": den_valido,
            f"{prefixo}_sem_bueiro": sem,
        },
        index=df.index,
    )


def calcular_d(
    domicilios: pd.Series, moradores: pd.Series, faces: pd.Series
) -> pd.DataFrame:
    trio = pd.concat(
        [
            domicilios.rename("D_dom_sem_bueiro"),
            moradores.rename("D_mor_sem_bueiro"),
            faces.rename("D_fac_sem_bueiro"),
        ],
        axis=1,
    )
    completo = trio.notna().all(axis=1)
    d_exp = trio[["D_dom_sem_bueiro", "D_mor_sem_bueiro"]].mean(axis=1).where(completo)
    d_priv = (0.5 * d_exp + 0.5 * trio["D_fac_sem_bueiro"]).where(completo)
    d = (1.0 - d_priv).rename("D")
    d1 = (1.0 - trio["D_mor_sem_bueiro"]).rename("D1")
    d3 = (1.0 - trio.mean(axis=1)).where(completo).rename("D3")
    for nome, serie in (("D", d), ("D1", d1), ("D3", d3)):
        _validar_01(serie, nome)
    return pd.concat([trio, d_exp.rename("D_exp"), d_priv.rename("D_priv"), d, d1, d3], axis=1)


def _preparar_setor(df: pd.DataFrame, *alternativas: str) -> pd.DataFrame:
    col = _coluna(df, *alternativas)
    out = df.copy()
    out["codigo_setor"] = out[col].astype("string").str.strip()
    if out["codigo_setor"].duplicated().any():
        dup = out.loc[out["codigo_setor"].duplicated(), "codigo_setor"].head().tolist()
        raise ValueError(f"Chave setorial duplicada: {dup}")
    return out.set_index("codigo_setor", drop=True)


def _arquivo_por_url(diretorio: Path, url: str) -> Path:
    path = diretorio / Path(urlparse(url).path).name
    if not path.exists():
        raise FileNotFoundError(f"Arquivo bruto esperado ausente: {path}")
    return path


def _resumo_cobertura(base: pd.DataFrame) -> dict[str, int | float]:
    resumo: dict[str, int | float] = {"universo": int(len(base))}
    for col in ("A", "E", "R", "D", "ISAU_C4", "ISAU_C3"):
        n = int(base[col].notna().sum())
        resumo[f"{col}_validos"] = n
        resumo[f"{col}_pct"] = float(100.0 * n / len(base))
    return resumo


def executar(raiz: Path) -> None:
    raiz = raiz.resolve()
    paths = resolve_paths(raiz)
    paths.create()
    manifesto = paths.manifests / "execucao.jsonl"

    qa05b_path = paths.qa / "etapa05b_inspecao_fontes_isau.json"
    if not qa05b_path.exists():
        raise FileNotFoundError(f"Gate 05b ausente: {qa05b_path}")
    qa05b = _carregar_json(qa05b_path)
    if qa05b.get("status") != "RESOLVIDO_AER_DRENAGEM":
        raise RuntimeError(
            "Gate 05c bloqueado: 05b deve ter status RESOLVIDO_AER_DRENAGEM; "
            f"status atual={qa05b.get('status')}"
        )

    universo_path = paths.processed / "setorial" / "base_renovacao_demografica_2022.parquet"
    if not universo_path.exists():
        raise FileNotFoundError(f"Universo setorial oficial ausente: {universo_path}")
    universo = pd.read_parquet(universo_path)
    chave_uni = _coluna(universo, "codigo_setor", "CD_SETOR")
    cod_muni = _coluna(universo, "codigo_ibge")
    universo = universo[[chave_uni, cod_muni]].copy()
    universo["codigo_setor"] = universo[chave_uni].astype("string").str.strip()
    universo["codigo_ibge"] = universo[cod_muni].astype("string").str.strip()
    universo = universo[["codigo_setor", "codigo_ibge"]].drop_duplicates()
    if len(universo) != REFERENCIA_CADERNO["universo"]:
        raise AssertionError(
            f"Universo setorial diverge do caderno: {len(universo)} != {REFERENCIA_CADERNO['universo']}"
        )
    if universo["codigo_setor"].duplicated().any():
        raise AssertionError("Universo oficial contém CD_SETOR duplicado.")
    chaves = set(universo["codigo_setor"].astype(str))
    indice_canonico = pd.Index(sorted(chaves), name="codigo_setor")

    raw_dom = paths.raw / "ibge" / "censo2022" / "isau" / "domicilios"
    raw_ent = paths.raw / "ibge" / "censo2022" / "isau" / "entorno"
    urls_dom = list(qa05b["arquivos_domiciliares"])
    dom1_url = next(u for u in urls_dom if "domicilio1" in Path(urlparse(u).path).name.casefold())
    dom2_url = next(u for u in urls_dom if "domicilio2" in Path(urlparse(u).path).name.casefold())

    dom1 = _preparar_setor(_ler_csv_zip(_arquivo_por_url(raw_dom, dom1_url)), "CD_setor", "setor")
    dom2 = _preparar_setor(_ler_csv_zip(_arquivo_por_url(raw_dom, dom2_url)), "CD_setor", "setor")
    dom1 = dom1.loc[dom1.index.isin(chaves)]
    dom2 = dom2.loc[dom2.index.isin(chaves)]
    cobertura_linhas_fontes = {
        "domicilio1_linhas_no_universo": int(len(dom1)),
        "domicilio1_ausentes_no_universo": int(len(chaves) - len(dom1)),
        "domicilio2_linhas_no_universo": int(len(dom2)),
        "domicilio2_ausentes_no_universo": int(len(chaves) - len(dom2)),
    }

    # A ausência de uma linha no arquivo temático não pode excluir o setor do universo.
    # O universo canônico é definido pelo Básico; arquivos temáticos são reindexados e
    # setores não publicados permanecem NaN, do mesmo modo que valores sob sigilo.
    dom1 = dom1.reindex(indice_canonico)
    dom2 = dom2.reindex(indice_canonico)

    aer = pd.DataFrame(index=indice_canonico)
    den = _numero(dom1[_coluna(dom1, "V00001")], "V00001")
    trabalho = pd.DataFrame(index=aer.index)
    trabalho["V00001"] = den
    for var in A_VARS + E_VARS + R_VARS:
        trabalho[var] = _numero(dom2[_coluna(dom2, var)], var)
    aer = pd.concat([aer, calcular_a(trabalho), calcular_e(trabalho), calcular_r(trabalho)], axis=1)

    codigos_bueiro = qa05b.get("codigos_bueiro_por_universo") or {}
    faltam_universos = sorted(set(("domicilios", "moradores", "faces")) - set(codigos_bueiro))
    if faltam_universos:
        raise RuntimeError(f"05b não resolveu códigos de drenagem para: {faltam_universos}")

    sem_bueiro: dict[str, pd.Series] = {}
    drenagem_audit = []
    prefixos = {"domicilios": "D_dom", "moradores": "D_mor", "faces": "D_fac"}
    chaves_alt = {
        "domicilios": ("CD_setor", "setor"),
        "moradores": ("CD_setor", "setor"),
        "faces": ("COD_SETOR_M22FINAL", "CD_setor", "setor"),
    }
    for universo_nome in ("domicilios", "moradores", "faces"):
        url = str(qa05b["arquivos_entorno"][universo_nome])
        df = _preparar_setor(
            _ler_csv_zip(_arquivo_por_url(raw_ent, url)), *chaves_alt[universo_nome]
        )
        df = df.loc[df.index.isin(chaves)]
        cobertura_linhas_fontes[f"entorno_{universo_nome}_linhas_no_universo"] = int(len(df))
        cobertura_linhas_fontes[f"entorno_{universo_nome}_ausentes_no_universo"] = int(
            len(chaves) - len(df)
        )
        df = df.reindex(indice_canonico)
        cod = codigos_bueiro[universo_nome]
        audit = calcular_sem_bueiro(
            df,
            sim=cod["sim"],
            nao=cod["nao"],
            nao_declarado=cod["nao_declarado"],
            prefixo=prefixos[universo_nome],
        )
        drenagem_audit.append(audit)
        sem_bueiro[universo_nome] = audit[f"{prefixos[universo_nome]}_sem_bueiro"]

    d_audit = pd.concat(drenagem_audit, axis=1)
    d_calc = calcular_d(
        sem_bueiro["domicilios"], sem_bueiro["moradores"], sem_bueiro["faces"]
    )
    d_metricas = d_calc[["D_exp", "D_priv", "D", "D1", "D3"]].copy()
    base = pd.concat([aer, d_audit, d_metricas], axis=1).reset_index()
    if base.columns.duplicated().any():
        duplicadas = base.columns[base.columns.duplicated()].tolist()
        raise AssertionError(f"Saída 05c contém colunas duplicadas: {duplicadas}")
    base = universo.merge(base, on="codigo_setor", how="left", validate="one_to_one")

    dominios = ["A", "E", "R", "D"]
    base["N_DOMINIOS_OBS"] = base[dominios].notna().sum(axis=1).astype("int64")
    base["FLAG_INCOMPLETO"] = base["N_DOMINIOS_OBS"] < 4
    base["DOMINIO_AUSENTE"] = base[dominios].apply(
        lambda row: "|".join(c for c in dominios if pd.isna(row[c])), axis=1
    )
    base["ISAU_C4"] = base[dominios].mean(axis=1, skipna=False).where(base["N_DOMINIOS_OBS"] == 4)
    base["ISAU_C3"] = base[dominios].mean(axis=1, skipna=True).where(base["N_DOMINIOS_OBS"] >= 3)
    base["PRIV_C4"] = 1.0 - base["ISAU_C4"]
    base["PRIV_C3"] = 1.0 - base["ISAU_C3"]
    for col in dominios + ["ISAU_C4", "ISAU_C3", "PRIV_C4", "PRIV_C3"]:
        _validar_01(base[col], col)

    municipios = carregar_municipios(raiz / "config/municipios.yml")
    nomes = {m.codigo_ibge: m.nome for m in municipios}
    base["municipio"] = base["codigo_ibge"].map(nomes)

    cobertura = _resumo_cobertura(base)
    cobertura["D1_validos"] = int(base["D1"].notna().sum())
    cobertura["D3_validos"] = int(base["D3"].notna().sum())
    comparacao = {
        chave: {
            "referencia_caderno": int(valor),
            "observado_pipeline": int(
                cobertura[
                    {
                        "universo": "universo",
                        "A_validos": "A_validos",
                        "E_validos": "E_validos",
                        "R_validos": "R_validos",
                        "D_validos": "D_validos",
                        "C4_validos": "ISAU_C4_validos",
                        "C3_validos": "ISAU_C3_validos",
                    }[chave]
                ]
            ),
        }
        for chave, valor in REFERENCIA_CADERNO.items()
    }
    for item in comparacao.values():
        item["diferenca"] = item["observado_pipeline"] - item["referencia_caderno"]

    cob_mun = (
        base.groupby(["codigo_ibge", "municipio"], dropna=False)
        .agg(
            setores=("codigo_setor", "size"),
            A_validos=("A", lambda s: int(s.notna().sum())),
            E_validos=("E", lambda s: int(s.notna().sum())),
            R_validos=("R", lambda s: int(s.notna().sum())),
            D_validos=("D", lambda s: int(s.notna().sum())),
            C4_validos=("ISAU_C4", lambda s: int(s.notna().sum())),
            C3_validos=("ISAU_C3", lambda s: int(s.notna().sum())),
        )
        .reset_index()
    )
    for col in ("A", "E", "R", "D", "C4", "C3"):
        cob_mun[f"{col}_pct"] = 100.0 * cob_mun[f"{col}_validos"] / cob_mun["setores"]

    saida_dir = paths.processed / "setorial"
    saida_dir.mkdir(parents=True, exist_ok=True)
    csv_path = saida_dir / "base_isau_2022.csv"
    parquet_path = saida_dir / "base_isau_2022.parquet"
    base.to_csv(csv_path, index=False, encoding="utf-8")
    base.to_parquet(parquet_path, index=False)
    registrar_arquivo(manifesto, csv_path, origem="Censo 2022 agregados por setor + entorno; Gate 05b")
    registrar_arquivo(manifesto, parquet_path, origem="Censo 2022 agregados por setor + entorno; Gate 05b")

    qa_dir = paths.qa
    cob_mun_path = qa_dir / "etapa05c_cobertura_municipal_isau.csv"
    cob_mun.to_csv(cob_mun_path, index=False, encoding="utf-8")
    registrar_arquivo(manifesto, cob_mun_path, origem="base_isau_2022")

    qa = {
        "status": "OK",
        "etapa": "05c",
        "formula": "ISAU_C4=media(A,E,R,D) se n=4; ISAU_C3=media dos dominios observados se n>=3; PRIV=1-ISAU",
        "agua": "A=1-media(V00464/V00001,V00200/V00001,V00201/V00001), minimo 2 medidas validas",
        "esgoto": "E=1-(V00312+V00313+V00314+V00315+V00316)/V00001",
        "residuos": "R=1-(V00399+V00400+V00401+V00402)/V00001",
        "drenagem_D2": "D=1-[0.5*media(Domicilios_sem_bueiro,Moradores_sem_bueiro)+0.5*Faces_sem_bueiro]",
        "denominador_drenagem": "em cada universo: nao/(sim+nao); nao declarado excluido do denominador substantivo",
        "codigos_drenagem": codigos_bueiro,
        "cobertura_linhas_fontes": cobertura_linhas_fontes,
        "cobertura": cobertura,
        "comparacao_referencia_caderno": comparacao,
        "politica_ausencias": "linha temática ausente, x/supressao e nao disponibilidade permanecem NaN; componentes aditivos E/R exigem todos os numeradores; A exige >=2/3; D2 exige os tres universos",
        "saidas": [
            str(csv_path.relative_to(paths.data_root)),
            str(parquet_path.relative_to(paths.data_root)),
            str(cob_mun_path.relative_to(paths.data_root)),
        ],
    }
    qa_path = qa_dir / "etapa05c_calculo_isau.json"
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    registrar_arquivo(manifesto, qa_path, origem="Gate 05c")
    registrar_evento(
        manifesto,
        {
            "tipo": "etapa",
            "etapa": "05c",
            "status": "OK",
            "cobertura": cobertura,
            "saida": str(parquet_path.relative_to(paths.data_root)),
        },
    )
    print(json.dumps(qa, ensure_ascii=False, indent=2))