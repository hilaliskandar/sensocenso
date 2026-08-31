from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

from .config import carregar_municipios
from .fontes.http import HttpClient
from .paths import resolve_paths
from .proveniencia import registrar_arquivo, registrar_evento


PADRAO_BASICO = re.compile(r"^Agregados_por_setores_basico_BR(?:_\d{8})?\.zip$", re.I)
PADRAO_DOM1 = re.compile(
    r"^Agregados_por_setores_caracteristicas_domicilio1_BR(?:_\d{8})?\.zip$", re.I
)
SIMBOLOS_SIGILO = {"x"}


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


def _ler_csv_zip(path: Path, token: str) -> pd.DataFrame:
    with zipfile.ZipFile(path) as zf:
        candidatos = [
            n for n in zf.namelist()
            if n.lower().endswith(".csv") and token.casefold() in n.casefold()
        ]
        if len(candidatos) != 1:
            raise ValueError(
                f"ZIP deve conter exatamente um CSV compatível com {token!r}; candidatos={candidatos}"
            )
        bruto = zf.read(candidatos[0])
    encoding = _detectar_encoding(bruto)
    sep = _detectar_separador(bruto, encoding)
    return pd.read_csv(io.BytesIO(bruto), sep=sep, dtype="string", encoding=encoding)


def _coluna(df: pd.DataFrame, *alternativas: str) -> str:
    mapa = {str(c).strip().casefold(): str(c) for c in df.columns}
    for alt in alternativas:
        achou = mapa.get(alt.strip().casefold())
        if achou is not None:
            return achou
    raise ValueError(f"Nenhuma das colunas esperadas foi encontrada: {alternativas}")


def _converter_preservando_sigilo(serie: pd.Series, nome: str) -> pd.Series:
    bruto = serie.astype("string").str.strip()
    # Os agregados 2022 do IBGE usam vírgula decimal em variáveis de média,
    # enquanto contagens permanecem inteiras. A normalização é feita somente
    # para a conversão numérica; o valor bruto segue intacto para o diagnóstico.
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
        raise ValueError(f"Valores não numéricos inesperados em {nome}: {inesperados}")
    return num


def _agregar_basico(zip_basico: Path, codigos: set[str]) -> pd.DataFrame:
    df = _ler_csv_zip(zip_basico, "basico")
    setor = _coluna(df, "CD_SETOR")
    pop = _coluna(df, "V0001", "V00001")
    tam = _coluna(df, "V0005", "V00005")
    dpo = _coluna(df, "V0007", "V00007")

    work = df[[setor, pop, tam, dpo]].copy()
    work["codigo_ibge"] = work[setor].astype("string").str.slice(0, 7)
    work = work.loc[work["codigo_ibge"].isin(codigos)].copy()
    work["pop_total_setor"] = _converter_preservando_sigilo(work[pop], pop)
    work["tam_medio_setor"] = _converter_preservando_sigilo(work[tam], tam)
    work["dpo_setor"] = _converter_preservando_sigilo(work[dpo], dpo)

    # V0005 é média setorial. Para obter a média municipal no mesmo universo de
    # domicílios particulares ocupados, pondera-se por V0007; não se calcula a
    # média simples das médias setoriais.
    work["moradores_dpo_estimado_setor"] = work["tam_medio_setor"] * work["dpo_setor"]
    work["basico_completo"] = work[["tam_medio_setor", "dpo_setor"]].notna().all(axis=1)

    linhas = []
    for codigo, g in work.groupby("codigo_ibge", sort=True):
        validos = g.loc[g["basico_completo"]].copy()
        if validos.empty:
            raise ValueError(f"Município {codigo} sem setor válido para DPO/tamanho médio 2022.")
        dpo_total = float(validos["dpo_setor"].sum())
        moradores = float(validos["moradores_dpo_estimado_setor"].sum())
        linhas.append(
            {
                "codigo_ibge": str(codigo),
                "ano": 2022,
                "dpo": dpo_total,
                "moradores_dpo": moradores,
                "tam_medio": moradores / dpo_total,
                "pop_total_setorial": float(g["pop_total_setor"].sum(min_count=1)),
                "setores_basico": int(len(g)),
                "setores_basico_completos": int(len(validos)),
                "cobertura_basico": float(len(validos) / len(g)),
            }
        )
    return pd.DataFrame(linhas)


def _agregar_unipessoais(zip_dom1: Path, codigos: set[str]) -> pd.DataFrame:
    df = _ler_csv_zip(zip_dom1, "domicilio1")
    setor = _coluna(df, "CD_SETOR")
    dpp = _coluna(df, "V00001")
    uni = _coluna(df, "V00017")

    work = df[[setor, dpp, uni]].copy()
    work["codigo_ibge"] = work[setor].astype("string").str.slice(0, 7)
    work = work.loc[work["codigo_ibge"].isin(codigos)].copy()
    work["dpp"] = _converter_preservando_sigilo(work[dpp], dpp)
    work["uni"] = _converter_preservando_sigilo(work[uni], uni)
    work["par_completo"] = work[["dpp", "uni"]].notna().all(axis=1)

    linhas = []
    for codigo, g in work.groupby("codigo_ibge", sort=True):
        validos = g.loc[g["par_completo"]].copy()
        if validos.empty:
            raise ValueError(f"Município {codigo} sem setor com V00001/V00017 simultaneamente públicos.")
        dpp_total = float(validos["dpp"].sum())
        uni_total = float(validos["uni"].sum())
        linhas.append(
            {
                "codigo_ibge": str(codigo),
                "dpp_num_moradores": dpp_total,
                "unipessoais": uni_total,
                "pct_unipessoais": uni_total / dpp_total,
                "setores_dom1": int(len(g)),
                "setores_dom1_completos": int(len(validos)),
                "cobertura_unipessoais": float(len(validos) / len(g)),
            }
        )
    return pd.DataFrame(linhas)


def _calcular_variacoes(painel: pd.DataFrame) -> pd.DataFrame:
    out = painel.sort_values(["codigo_ibge", "ano"]).copy()
    for coluna, prefixo in (
        ("dpo", "dpo"),
        ("moradores_dpo", "moradores"),
        ("tam_medio", "tam_medio"),
        ("pct_unipessoais", "pct_unipessoais"),
    ):
        out[f"{prefixo}_anterior"] = out.groupby("codigo_ibge")[coluna].shift(1)
        if coluna == "pct_unipessoais":
            out[f"var_{prefixo}_pp"] = (out[coluna] - out[f"{prefixo}_anterior"]) * 100.0
        elif coluna == "tam_medio":
            out[f"var_{prefixo}_abs"] = out[coluna] - out[f"{prefixo}_anterior"]
        else:
            out[f"crescimento_{prefixo}_pct"] = (
                out[coluna] / out[f"{prefixo}_anterior"] - 1.0
            ) * 100.0
    out["divergencia_crescimento_domicilios_moradores_pp"] = (
        out["crescimento_dpo_pct"] - out["crescimento_moradores_pct"]
    )
    return out


def executar(raiz: Path) -> None:
    raiz = raiz.resolve()
    paths = resolve_paths(raiz)
    paths.create()
    municipios = carregar_municipios(raiz / "config/municipios.yml")
    codigos = {m.codigo_ibge for m in municipios}
    nomes = {m.codigo_ibge: m.nome for m in municipios}
    manifesto = paths.manifests / "execucao.jsonl"

    historico_path = paths.processed / "municipal" / "base_domiciliar_historica_2000_2010.parquet"
    if not historico_path.exists():
        raise FileNotFoundError(
            f"Base domiciliar histórica ausente: {historico_path}. Execute primeiro --etapa 03b."
        )

    snapshot = paths.raw / "ibge" / "indices_publicacao" / "censo2022_agregados_setor.json"
    if not snapshot.exists():
        raise FileNotFoundError(f"Snapshot Censo 2022 ausente: {snapshot}. Execute primeiro --etapa 01.")
    links = _carregar_links_snapshot(snapshot)
    url_basico = _selecionar_unico(links, PADRAO_BASICO, "arquivo Básico 2022")
    url_dom1 = _selecionar_unico(links, PADRAO_DOM1, "Características do domicílio 1 2022")

    raw_dir = paths.raw / "ibge" / "censo2022" / "agregados_setor"
    raw_dir.mkdir(parents=True, exist_ok=True)
    cliente = HttpClient(timeout=600)
    zip_basico = _baixar_se_ausente(
        cliente, url_basico, raw_dir / Path(urlparse(url_basico).path).name, manifesto
    )
    zip_dom1 = _baixar_se_ausente(
        cliente, url_dom1, raw_dir / Path(urlparse(url_dom1).path).name, manifesto
    )

    basico = _agregar_basico(zip_basico, codigos)
    unip = _agregar_unipessoais(zip_dom1, codigos)
    base2022 = basico.merge(unip, on="codigo_ibge", how="outer", validate="one_to_one")
    observados = set(base2022["codigo_ibge"].astype(str))
    if observados != codigos:
        raise ValueError(
            f"Universo domiciliar 2022 diverge: faltantes={sorted(codigos-observados)}, "
            f"extras={sorted(observados-codigos)}"
        )
    base2022["municipio"] = base2022["codigo_ibge"].map(nomes)

    historico = pd.read_parquet(historico_path)
    manter = [
        "codigo_ibge", "municipio", "ano", "dpo", "moradores_dpo", "tam_medio",
        "dpp_num_moradores", "unipessoais", "pct_unipessoais",
    ]
    faltantes = [c for c in manter if c not in historico.columns]
    if faltantes:
        raise ValueError(f"Base histórica sem colunas necessárias: {faltantes}")

    painel = pd.concat([historico[manter], base2022[manter]], ignore_index=True)
    if len(painel) != 90 or painel["codigo_ibge"].nunique() != 30:
        raise AssertionError("Painel domiciliar 2000–2010–2022 não fechou em 30×3.")
    if not (painel.groupby("codigo_ibge")["ano"].nunique() == 3).all():
        raise AssertionError("Há município sem os três censos no painel domiciliar.")
    if painel[["dpo", "moradores_dpo", "tam_medio", "dpp_num_moradores", "unipessoais", "pct_unipessoais"]].isna().any().any():
        raise ValueError("Há lacunas nas métricas domiciliares do painel 30×3.")
    if not painel["pct_unipessoais"].between(0, 1).all():
        raise ValueError("Participação de unipessoais fora de [0,1].")

    painel = _calcular_variacoes(painel)
    destino = paths.processed / "municipal"
    csv = destino / "base_domiciliar_2000_2010_2022.csv"
    parquet = destino / "base_domiciliar_2000_2010_2022.parquet"
    painel.to_csv(csv, index=False, encoding="utf-8")
    painel.to_parquet(parquet, index=False)
    registrar_arquivo(manifesto, csv, origem="SIDRA 156/185 + Censo 2022 Básico e Características do domicílio 1")
    registrar_arquivo(manifesto, parquet, origem="SIDRA 156/185 + Censo 2022 Básico e Características do domicílio 1")

    cobertura = base2022[
        [
            "codigo_ibge", "municipio", "setores_basico", "setores_basico_completos",
            "cobertura_basico", "setores_dom1", "setores_dom1_completos", "cobertura_unipessoais",
        ]
    ].sort_values("codigo_ibge")
    cobertura_path = paths.qa / "etapa03c_cobertura_domicilios_2022.csv"
    cobertura.to_csv(cobertura_path, index=False, encoding="utf-8")

    linhas_2022 = painel.loc[painel["ano"].eq(2022)].copy()
    qa = {
        "status": "OK",
        "linhas": int(len(painel)),
        "municipios": int(painel["codigo_ibge"].nunique()),
        "anos": sorted(int(x) for x in painel["ano"].unique()),
        "fonte_dpo_tamanho_2022": "Censo 2022 Agregados por Setores - Básico: V0007 e V0005",
        "fonte_unipessoais_2022": "Censo 2022 Características do domicílio 1: V00001 e V00017",
        "regra_sigilo_unipessoais": (
            "percentual calculado somente sobre setores em que V00001 e V00017 são simultaneamente públicos; "
            "x/X permanece ausente e não é reconstruído por diferença"
        ),
        "cobertura_basico_min": float(base2022["cobertura_basico"].min()),
        "cobertura_unipessoais_min": float(base2022["cobertura_unipessoais"].min()),
        "divergencia_crescimento_2010_2022_min_pp": float(
            linhas_2022["divergencia_crescimento_domicilios_moradores_pp"].min()
        ),
        "divergencia_crescimento_2010_2022_max_pp": float(
            linhas_2022["divergencia_crescimento_domicilios_moradores_pp"].max()
        ),
        "municipios_divergencia_positiva_2010_2022": int(
            (linhas_2022["divergencia_crescimento_domicilios_moradores_pp"] > 0).sum()
        ),
        "queda_tamanho_medio_2010_2022": int((linhas_2022["var_tam_medio_abs"] < 0).sum()),
        "aumento_unipessoais_2010_2022": int((linhas_2022["var_pct_unipessoais_pp"] > 0).sum()),
        "url_basico": url_basico,
        "url_domicilio1": url_dom1,
        "saida_cobertura_csv": str(cobertura_path.relative_to(paths.data_root)),
        "saida_csv": str(csv.relative_to(paths.data_root)),
        "saida_parquet": str(parquet.relative_to(paths.data_root)),
    }
    qa_path = paths.qa / "etapa03c_domicilios_2022_integracao.json"
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    registrar_evento(manifesto, {"tipo": "etapa", "etapa": "03c", **qa})
    print(json.dumps(qa, ensure_ascii=False, indent=2))
