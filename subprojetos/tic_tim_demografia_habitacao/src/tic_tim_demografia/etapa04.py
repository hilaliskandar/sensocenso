from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

from .config import carregar_municipios
from .fontes.censo2022 import ler_setores_urbanos_basico_zip
from .fontes.http import HttpClient
from .paths import resolve_paths
from .proveniencia import registrar_arquivo, registrar_evento


PADRAO_DEMOGRAFIA = re.compile(r"^Agregados_por_setores_demografia_BR(?:_\d{8})?\.zip$", re.I)
SIMBOLOS_SIGILO = {"x"}
COLUNAS_RENOVACAO = [
    "V01006",  # população total
    "V01008",  # mulheres
    "V01023",  # mulheres 15-19
    "V01024",  # mulheres 20-24
    "V01025",  # mulheres 25-29
    "V01026",  # mulheres 30-39
    "V01027",  # mulheres 40-49
    "V01031",  # população 0-4
]


def _carregar_links_snapshot(path: Path) -> list[str]:
    dados = json.loads(path.read_text(encoding="utf-8"))
    links = dados.get("links") if isinstance(dados, dict) else None
    if not isinstance(links, list):
        raise ValueError(f"Snapshot de índice inválido: {path}")
    return [str(x) for x in links]


def _selecionar_unico(links: list[str], padrao: re.Pattern[str], descricao: str) -> str:
    candidatos = []
    for link in links:
        nome = Path(urlparse(link).path).name
        if padrao.match(nome):
            candidatos.append(link)
    if len(candidatos) != 1:
        raise ValueError(f"Seleção ambígua/ausente para {descricao}: {candidatos}")
    return candidatos[0]


def _baixar_se_ausente(cliente: HttpClient, url: str, destino: Path, manifesto: Path) -> Path:
    if destino.exists():
        return destino
    return cliente.baixar_arquivo(url, destino, manifesto=manifesto)


def _detectar_encoding(bruto: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin1"):
        try:
            bruto.decode(encoding, errors="strict")
            return encoding
        except UnicodeDecodeError:
            continue
    raise ValueError("Codificação CSV não reconhecida.")


def _detectar_separador(bruto: bytes, encoding: str) -> str:
    primeira = bruto[:65536].decode(encoding, errors="strict").splitlines()[0]
    contagens = {";": primeira.count(";"), ",": primeira.count(","), "\t": primeira.count("\t")}
    sep, n = max(contagens.items(), key=lambda x: x[1])
    if n == 0:
        raise ValueError("Separador CSV não reconhecido.")
    return sep


def _ler_demografia_renovacao(path: Path, codigos: set[str]) -> pd.DataFrame:
    with zipfile.ZipFile(path) as zf:
        candidatos = [
            n for n in zf.namelist()
            if n.lower().endswith(".csv") and "demografia" in n.casefold()
        ]
        if len(candidatos) != 1:
            raise ValueError(f"ZIP de demografia deve conter um CSV; candidatos={candidatos}")
        bruto = zf.read(candidatos[0])
    encoding = _detectar_encoding(bruto)
    sep = _detectar_separador(bruto, encoding)
    df = pd.read_csv(io.BytesIO(bruto), sep=sep, dtype="string", encoding=encoding)
    mapa = {str(c).strip().casefold(): str(c) for c in df.columns}
    setor = mapa.get("cd_setor")
    if setor is None:
        raise ValueError("Arquivo Demografia 2022 sem CD_SETOR.")
    faltantes = [c for c in COLUNAS_RENOVACAO if c not in df.columns]
    if faltantes:
        raise ValueError(f"Variáveis necessárias à renovação 2022 ausentes: {faltantes}")
    work = df[[setor] + COLUNAS_RENOVACAO].copy()
    work["codigo_ibge"] = work[setor].astype("string").str.slice(0, 7)
    work = work.loc[work["codigo_ibge"].isin(codigos)].copy()
    if work[setor].duplicated().any():
        raise ValueError("CD_SETOR duplicado no arquivo Demografia 2022.")
    return work.rename(columns={setor: "codigo_setor"})


def _converter_coluna(serie: pd.Series, nome: str) -> pd.Series:
    bruto = serie.astype("string").str.strip()
    num = pd.to_numeric(bruto, errors="coerce")
    mask = num.isna() & bruto.notna()
    inesperados = sorted(
        {
            str(x)
            for x in bruto.loc[mask].dropna().tolist()
            if str(x).casefold() not in SIMBOLOS_SIGILO
        }
    )
    if inesperados:
        raise ValueError(f"Valores não numéricos inesperados em {nome}: {inesperados}")
    return num


def _derivar_setores(universo_urbano: pd.DataFrame, demografia: pd.DataFrame) -> pd.DataFrame:
    base = universo_urbano[["codigo_setor", "codigo_ibge"]].copy()
    dem = demografia[["codigo_setor", "codigo_ibge"] + COLUNAS_RENOVACAO].copy()
    if base["codigo_setor"].duplicated().any() or dem["codigo_setor"].duplicated().any():
        raise ValueError("Chave setorial duplicada antes da integração da etapa 04.")
    work = base.merge(
        dem.drop(columns=["codigo_ibge"]),
        on="codigo_setor",
        how="left",
        validate="one_to_one",
        indicator="presenca_demografia",
    )
    work["tem_linha_demografia"] = work["presenca_demografia"].eq("both")
    work = work.drop(columns=["presenca_demografia"])

    for coluna in COLUNAS_RENOVACAO:
        work[coluna] = _converter_coluna(work[coluna], coluna)

    cols_m1549 = ["V01023", "V01024", "V01025", "V01026", "V01027"]
    work["valido_m1549"] = work[cols_m1549].notna().all(axis=1)
    work["mulheres_15_49"] = work[cols_m1549].sum(axis=1, min_count=len(cols_m1549))
    work["mulheres_15_29"] = work[["V01023", "V01024", "V01025"]].sum(axis=1, min_count=3)
    work["mulheres_30_49"] = work[["V01026", "V01027"]].sum(axis=1, min_count=2)
    work["mulheres_20_39"] = work[["V01024", "V01025", "V01026"]].sum(axis=1, min_count=3)
    work["criancas_0_4"] = work["V01031"]
    work["valido_cwr"] = work["valido_m1549"] & work["criancas_0_4"].notna() & work["mulheres_15_49"].gt(0)

    work["pct_m1549_pop"] = (
        work["mulheres_15_49"] / work["V01006"] * 100.0
    ).where(work["valido_m1549"] & work["V01006"].gt(0))
    work["pct_m1549_mulheres"] = (
        work["mulheres_15_49"] / work["V01008"] * 100.0
    ).where(work["valido_m1549"] & work["V01008"].gt(0))
    work["cwr_0_4_por_1000_m1549"] = (
        work["criancas_0_4"] / work["mulheres_15_49"] * 1000.0
    ).where(work["valido_cwr"])
    work["razao_m15_29_m30_49"] = (
        work["mulheres_15_29"] / work["mulheres_30_49"] * 100.0
    ).where(work["valido_m1549"] & work["mulheres_30_49"].gt(0))
    work["pct_m20_39_entre_m1549"] = (
        work["mulheres_20_39"] / work["mulheres_15_49"] * 100.0
    ).where(work["valido_m1549"] & work["mulheres_15_49"].gt(0))
    return work


def _agregar_municipios(setores: pd.DataFrame, nomes: dict[str, str]) -> pd.DataFrame:
    linhas = []
    for codigo, g in setores.groupby("codigo_ibge", sort=True):
        gm = g.loc[g["valido_m1549"]].copy()
        gc = g.loc[g["valido_cwr"]].copy()
        if gm.empty or gc.empty:
            raise ValueError(f"Município {codigo} sem universo válido para M15-49/CWR.")

        m1549 = float(gm["mulheres_15_49"].sum())
        m1529 = float(gm["mulheres_15_29"].sum())
        m3049 = float(gm["mulheres_30_49"].sum())
        m2039 = float(gm["mulheres_20_39"].sum())
        pop_validos = float(gm["V01006"].sum(min_count=1))
        mulheres_validas = float(gm["V01008"].sum(min_count=1))
        pop_publicada = float(g["V01006"].sum(min_count=1))
        criancas_cwr = float(gc["criancas_0_4"].sum())
        m1549_cwr = float(gc["mulheres_15_49"].sum())

        linhas.append(
            {
                "codigo_ibge": str(codigo),
                "municipio": nomes[str(codigo)],
                "ano": 2022,
                "setores_urbanos": int(len(g)),
                "setores_com_demografia": int(g["tem_linha_demografia"].sum()),
                "setores_validos_m1549": int(g["valido_m1549"].sum()),
                "setores_validos_cwr": int(g["valido_cwr"].sum()),
                "cobertura_setorial_m1549": float(g["valido_m1549"].mean()),
                "cobertura_setorial_cwr": float(g["valido_cwr"].mean()),
                "pop_setores_validos_m1549": pop_validos,
                "pop_total_publicada": pop_publicada,
                "cobertura_pop_m1549": pop_validos / pop_publicada if pop_publicada > 0 else pd.NA,
                "mulheres_15_49_validas": m1549,
                "pct_m1549_pop": m1549 / pop_validos * 100.0 if pop_validos > 0 else pd.NA,
                "pct_m1549_mulheres": m1549 / mulheres_validas * 100.0 if mulheres_validas > 0 else pd.NA,
                "cwr_0_4_por_1000_m1549": criancas_cwr / m1549_cwr * 1000.0,
                "razao_m15_29_m30_49": m1529 / m3049 * 100.0 if m3049 > 0 else pd.NA,
                "pct_m20_39_entre_m1549": m2039 / m1549 * 100.0 if m1549 > 0 else pd.NA,
            }
        )
    return pd.DataFrame(linhas)


def _regressao_oraculo(produzido: pd.DataFrame, path: Path) -> dict:
    ref = pd.read_csv(path, dtype={"codigo_ibge": "string"})
    campos = [
        "cwr_0_4_por_1000_m1549",
        "razao_m15_29_m30_49",
        "pct_m20_39_entre_m1549",
    ]
    obrigatorias = ["codigo_ibge"] + campos
    faltantes = [c for c in obrigatorias if c not in ref.columns]
    if faltantes:
        raise ValueError(f"Oráculo de renovação sem colunas: {faltantes}")
    comp = ref.merge(
        produzido[["codigo_ibge"] + campos],
        on="codigo_ibge",
        how="left",
        suffixes=("_ref", "_prod"),
        validate="one_to_one",
        indicator=True,
    )
    if not comp["_merge"].eq("both").all():
        raise AssertionError("Há município do oráculo ausente no produto da etapa 04.")
    divergencias = []
    for campo in campos:
        dif = (comp[f"{campo}_prod"] - comp[f"{campo}_ref"]).abs()
        ruins = comp.loc[dif.gt(1e-9), ["codigo_ibge", f"{campo}_ref", f"{campo}_prod"]]
        for _, r in ruins.iterrows():
            divergencias.append(
                {
                    "codigo_ibge": str(r["codigo_ibge"]),
                    "campo": campo,
                    "referencia": float(r[f"{campo}_ref"]),
                    "produzido": float(r[f"{campo}_prod"]),
                }
            )
    if divergencias:
        raise AssertionError(f"Gate de regressão CWR reprovado: {divergencias[:20]}")
    return {
        "status": "OK",
        "municipios_oraculo": int(ref["codigo_ibge"].nunique()),
        "campos_comparados": campos,
        "divergencias": 0,
    }


def executar(raiz: Path) -> None:
    raiz = raiz.resolve()
    paths = resolve_paths(raiz)
    paths.create()
    municipios = carregar_municipios(raiz / "config/municipios.yml")
    codigos = {m.codigo_ibge for m in municipios}
    nomes = {m.codigo_ibge: m.nome for m in municipios}
    manifesto = paths.manifests / "execucao.jsonl"

    snapshot = paths.raw / "ibge" / "indices_publicacao" / "censo2022_agregados_setor.json"
    if not snapshot.exists():
        raise FileNotFoundError(f"Snapshot Censo 2022 ausente: {snapshot}. Execute primeiro --etapa 01.")
    links = _carregar_links_snapshot(snapshot)
    url_demografia = _selecionar_unico(links, PADRAO_DEMOGRAFIA, "arquivo Demografia por setor 2022")

    raw_dir = paths.raw / "ibge" / "censo2022" / "agregados_setor"
    cliente = HttpClient(timeout=600)
    zip_demografia = _baixar_se_ausente(
        cliente, url_demografia, raw_dir / Path(urlparse(url_demografia).path).name, manifesto
    )
    basicos = sorted(raw_dir.glob("Agregados_por_setores_basico_BR*.zip"))
    if len(basicos) != 1:
        raise ValueError(f"Arquivo Básico 2022 ausente/ambíguo em {raw_dir}: {basicos}")

    urbanos = ler_setores_urbanos_basico_zip(basicos[0], codigos_municipais=codigos)
    demografia = _ler_demografia_renovacao(zip_demografia, codigos)
    setores = _derivar_setores(urbanos, demografia)
    municipal = _agregar_municipios(setores, nomes)

    if len(urbanos) != 9087:
        raise AssertionError(f"Universo urbano canônico esperado=9087; observado={len(urbanos)}")
    if municipal["codigo_ibge"].nunique() != 30 or len(municipal) != 30:
        raise AssertionError("A etapa 04 não fechou em 30 municípios.")

    regressao = _regressao_oraculo(
        municipal, raiz / "tests/fixtures/oraculo_renovacao_2022_sentinelas.csv"
    )

    setorial_dir = paths.processed / "setorial"
    municipal_dir = paths.processed / "municipal"
    setorial_dir.mkdir(parents=True, exist_ok=True)
    municipal_dir.mkdir(parents=True, exist_ok=True)
    set_csv = setorial_dir / "base_renovacao_demografica_2022.csv"
    set_parquet = setorial_dir / "base_renovacao_demografica_2022.parquet"
    mun_csv = municipal_dir / "base_renovacao_demografica_2022.csv"
    mun_parquet = municipal_dir / "base_renovacao_demografica_2022.parquet"
    setores.to_csv(set_csv, index=False, encoding="utf-8")
    setores.to_parquet(set_parquet, index=False)
    municipal.to_csv(mun_csv, index=False, encoding="utf-8")
    municipal.to_parquet(mun_parquet, index=False)
    for arquivo in (set_csv, set_parquet, mun_csv, mun_parquet):
        registrar_arquivo(
            manifesto,
            arquivo,
            origem="Censo 2022 Agregados por Setores — Básico + Demografia",
        )

    qa = {
        "status": "OK",
        "etapa": "04",
        "interpretacao": (
            "CWR é proxy censitária de renovação demográfica recente; não é taxa de fecundidade, "
            "taxa total de fecundidade ou taxa de natalidade"
        ),
        "setores_urbanos_canonicos": int(len(setores)),
        "setores_com_demografia": int(setores["tem_linha_demografia"].sum()),
        "setores_validos_m1549": int(setores["valido_m1549"].sum()),
        "setores_validos_cwr": int(setores["valido_cwr"].sum()),
        "cobertura_setorial_m1549": float(setores["valido_m1549"].mean()),
        "cobertura_setorial_cwr": float(setores["valido_cwr"].mean()),
        "municipios": int(len(municipal)),
        "cwr_regional_ponderado": float(
            setores.loc[setores["valido_cwr"], "criancas_0_4"].sum()
            / setores.loc[setores["valido_cwr"], "mulheres_15_49"].sum()
            * 1000.0
        ),
        "regressao_oraculo": regressao,
        "regra_sigilo": (
            "x/X permanece ausente; M15-49 exige V01023–V01027 simultaneamente publicados; "
            "CWR exige ainda V01031 publicado e denominador positivo; não há imputação nem reconstrução"
        ),
        "saida_setorial_csv": str(set_csv.relative_to(paths.data_root)),
        "saida_municipal_csv": str(mun_csv.relative_to(paths.data_root)),
    }
    qa_path = paths.qa / "etapa04_renovacao_demografica_2022.json"
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    registrar_evento(manifesto, {"tipo": "etapa", **qa})
    print(json.dumps(qa, ensure_ascii=False, indent=2))
