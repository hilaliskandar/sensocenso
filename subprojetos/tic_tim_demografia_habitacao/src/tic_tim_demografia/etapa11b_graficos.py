"""Etapa 11b: gráficos públicos reprodutíveis do diagnóstico TIC–TIM.

Os gráficos são gerados de forma determinística a partir das bases produzidas
pelas etapas anteriores do pipeline. A única exceção técnica é G09: como a
síntese municipal da etapa 10 preserva proporções, mas não os numeradores e
denominadores de cada componente, a etapa 11b reabre os mesmos agregados
oficiais já adquiridos no pipeline para reconstruir e persistir uma base
regional explícita antes da renderização.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "tic-tim-demografia-etapa11b"
matplotlib.rcParams["font.family"] = "DejaVu Sans"

from matplotlib import pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402


FIGSIZE = (8.27, 5.6)
FIGSIZE_TALL = (8.27, 9.2)
DPI = 220

FONTES = {
    "G02": "Elaborado a partir de IBGE, Censos Demográficos 2000, 2010 e 2022.",
    "G03": "Elaborado a partir de IBGE, Censos Demográficos 2010 e 2022.",
    "G04": "Elaborado a partir de IBGE, Censos Demográficos 2010 e 2022.",
    "G05": "Elaborado a partir de IBGE, Censos Demográficos 2000, 2010 e 2022.",
    "G06": "Elaborado a partir de IBGE, Censos Demográficos 2000, 2010 e 2022.",
    "G09": "Elaborado a partir de IBGE, Censo Demográfico 2022.",
    "G11": "Elaborado a partir de IBGE, Censo Demográfico 2022.",
    "G12": "Elaboração própria a partir de IBGE, Censo Demográfico 2022.",
    "G13": "Elaboração própria a partir de IBGE, Censos Demográficos 2010 e 2022.",
}

TITULOS = {
    "G02": "Mudança da estrutura etária entre 2000 e 2022",
    "G03": "Crescimento populacional e envelhecimento",
    "G04": "Crescimento dos domicílios e da população, 2010–2022",
    "G05": "Redução do tamanho médio dos domicílios, 2000–2022",
    "G06": "Crescimento dos domicílios unipessoais, 2000–2022",
    "G09": "Composição das carências físico-sanitárias",
    "G11": "Participação preta e parda e carências físico-urbanas nos 30 municípios",
    "G12": "Carências físico-sanitárias e carências do entorno",
    "G13": "Crescimento domiciliar e gravidade físico-urbana nos 30 municípios",
}

NOTAS = {
    "G02": "Participações calculadas sobre a população total harmonizada das três faixas etárias.",
    "G03": "Dispersão descritiva; não implica relação causal.",
    "G04": "A linha diagonal representa igualdade entre os dois crescimentos.",
    "G05": "Unidade: pessoas por domicílio particular ocupado.",
    "G06": "Números absolutos e participação percentual são apresentados separadamente.",
    "G09": "As ocorrências podem se sobrepor e não representam famílias únicas.",
    "G11": "Spearman descritivo em escala municipal; associação ecológica e não causal.",
    "G12": "Índices comparativos relativos de 0 a 1; não são percentuais.",
    "G13": "Spearman descritivo em escala municipal; associação não causal.",
}

G09_ROTULOS = {
    "agua_fora_rede": "Água fora da rede geral",
    "agua_sem_canalizacao": "Água sem canalização interna",
    "sem_banheiro_ou_sanitario": "Sem banheiro exclusivo ou sanitário",
    "esgotamento_inadequado": "Esgotamento inadequado",
    "residuo_inadequado": "Resíduos inadequados",
    "precariedade_fisica": "Precariedade física estrita",
}


def _limpar_municipio(serie: pd.Series) -> pd.Series:
    return serie.astype("string").str.replace(r"\s*\(SP\)$", "", regex=True)


def _verificar_30(df: pd.DataFrame, *, codigo: str = "codigo_ibge", nome: str) -> None:
    if len(df) != 30 or df[codigo].astype("string").nunique() != 30:
        raise AssertionError(f"{nome} exige 30 municípios únicos; obtidos={len(df)}")


def _spearman(x: pd.Series, y: pd.Series) -> dict[str, float | int]:
    tab = pd.concat(
        [pd.to_numeric(x, errors="coerce"), pd.to_numeric(y, errors="coerce")],
        axis=1,
    ).dropna()
    if len(tab) < 3:
        raise ValueError("Spearman exige ao menos três pares válidos.")
    rho, p = spearmanr(tab.iloc[:, 0].to_numpy(), tab.iloc[:, 1].to_numpy())
    return {"n": int(len(tab)), "rho": float(rho), "p_valor": float(p)}


def _crescimento(v0: pd.Series, v1: pd.Series) -> pd.Series:
    v0 = pd.to_numeric(v0, errors="coerce")
    v1 = pd.to_numeric(v1, errors="coerce")
    return (100.0 * (v1 / v0 - 1.0)).where(v0.gt(0))


def _selecionar_rotulos_extremos(
    df: pd.DataFrame,
    x: str,
    y: str,
    *,
    n_por_extremo: int = 2,
) -> list[int]:
    idx: set[int] = set()
    for coluna in (x, y):
        validos = pd.to_numeric(df[coluna], errors="coerce").dropna()
        idx.update(validos.nsmallest(n_por_extremo).index.tolist())
        idx.update(validos.nlargest(n_por_extremo).index.tolist())
    return sorted(idx)


def _rodape(fig: plt.Figure, codigo: str, *, extra: str | None = None) -> None:
    fig.suptitle(TITULOS[codigo], x=0.08, ha="left", fontsize=13, fontweight="bold")
    texto = f"Fonte: {FONTES[codigo]}\nNota: {NOTAS[codigo]}"
    if extra:
        texto += f" {extra}"
    fig.text(0.08, 0.015, texto, ha="left", va="bottom", fontsize=8.2)


def _salvar(fig: plt.Figure, destino: Path, codigo: str) -> list[Path]:
    destino.mkdir(parents=True, exist_ok=True)
    png = destino / f"{codigo}.png"
    svg = destino / f"{codigo}.svg"
    fig.savefig(
        png,
        dpi=DPI,
        bbox_inches="tight",
        metadata={"Software": "tic_tim_demografia_etapa11b"},
    )
    fig.savefig(
        svg,
        bbox_inches="tight",
        metadata={"Date": None, "Creator": "tic_tim_demografia_etapa11b"},
    )
    plt.close(fig)
    return [png, svg]


def dados_g02(longitudinal: pd.DataFrame) -> pd.DataFrame:
    base = longitudinal.copy()
    anos = [2000, 2010, 2022]
    base["ano"] = pd.to_numeric(base["ano"], errors="coerce")
    if set(base["ano"].dropna().astype(int)) != set(anos):
        raise ValueError("G02 exige os anos 2000, 2010 e 2022.")
    linhas = []
    for ano in anos:
        sub = base.loc[base["ano"].eq(ano)]
        totais = sub[["pop_0_14", "pop_15_59", "pop_60_mais"]].apply(
            pd.to_numeric, errors="coerce"
        ).sum()
        total = float(totais.sum())
        if total <= 0:
            raise ValueError(f"G02 sem população válida em {ano}.")
        linhas.append(
            {
                "ano": ano,
                "pct_0_14": 100.0 * float(totais["pop_0_14"]) / total,
                "pct_15_59": 100.0 * float(totais["pop_15_59"]) / total,
                "pct_60_mais": 100.0 * float(totais["pop_60_mais"]) / total,
                "pop_total": int(round(total)),
            }
        )
    out = pd.DataFrame(linhas)
    if not np.allclose(out[["pct_0_14", "pct_15_59", "pct_60_mais"]].sum(axis=1), 100.0):
        raise AssertionError("G02: participações etárias não somam 100%.")
    return out


def plot_g02(dados: pd.DataFrame, destino: Path) -> list[Path]:
    fig, ax = plt.subplots(figsize=FIGSIZE)
    x = np.arange(len(dados))
    baixo = np.zeros(len(dados), dtype=float)
    for coluna, rotulo in (
        ("pct_0_14", "0–14 anos"),
        ("pct_15_59", "15–59 anos"),
        ("pct_60_mais", "60 anos ou mais"),
    ):
        valores = dados[coluna].to_numpy(dtype=float)
        ax.bar(x, valores, bottom=baixo, label=rotulo)
        for i, (b, v) in enumerate(zip(baixo, valores, strict=True)):
            if v >= 5:
                ax.text(i, b + v / 2, f"{v:.1f}%", ha="center", va="center", fontsize=8)
        baixo += valores
    ax.set_xticks(x, dados["ano"].astype(str))
    ax.set_ylabel("Participação na população regional (%)")
    ax.set_ylim(0, 100)
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.04))
    ax.spines[["top", "right"]].set_visible(False)
    _rodape(fig, "G02")
    fig.subplots_adjust(top=0.82, bottom=0.16)
    return _salvar(fig, destino, "G02")


def dados_g03(longitudinal: pd.DataFrame) -> pd.DataFrame:
    base = longitudinal.copy()
    base["codigo_ibge"] = base["codigo_ibge"].astype("string")
    base["ano"] = pd.to_numeric(base["ano"], errors="coerce")
    p10 = base.loc[base["ano"].eq(2010)].set_index("codigo_ibge")
    p22 = base.loc[base["ano"].eq(2022)].set_index("codigo_ibge")
    codigos = p22.index.intersection(p10.index)
    out = pd.DataFrame(index=codigos)
    out["municipio"] = p22["municipio_config"].reindex(codigos).astype("string")
    out["crescimento_pop_2010_2022_pct"] = _crescimento(
        p10["pop_total_harmonizada"].reindex(codigos),
        p22["pop_total_harmonizada"].reindex(codigos),
    )
    out["razao_envelhecimento_2022"] = pd.to_numeric(
        p22["razao_envelhecimento"].reindex(codigos), errors="coerce"
    )
    out = out.reset_index()
    _verificar_30(out, nome="G03")
    return out.sort_values("municipio").reset_index(drop=True)


def plot_g03(dados: pd.DataFrame, destino: Path) -> list[Path]:
    fig, ax = plt.subplots(figsize=FIGSIZE)
    x = dados["crescimento_pop_2010_2022_pct"]
    y = dados["razao_envelhecimento_2022"]
    ax.scatter(x, y, s=34)
    for i in _selecionar_rotulos_extremos(dados, "crescimento_pop_2010_2022_pct", "razao_envelhecimento_2022"):
        linha = dados.loc[i]
        ax.annotate(
            str(linha["municipio"]),
            (linha["crescimento_pop_2010_2022_pct"], linha["razao_envelhecimento_2022"]),
            xytext=(4, 4),
            textcoords="offset points",
            fontsize=7.4,
        )
    ax.axvline(0, linewidth=0.8)
    ax.set_xlabel("Crescimento populacional 2010–2022 (%)")
    ax.set_ylabel("Razão de envelhecimento em 2022\n(60+ por 100 pessoas de 0–14 anos)")
    ax.spines[["top", "right"]].set_visible(False)
    _rodape(fig, "G03")
    fig.subplots_adjust(top=0.82, bottom=0.20)
    return _salvar(fig, destino, "G03")


def dados_g04(longitudinal: pd.DataFrame, domicilios: pd.DataFrame) -> pd.DataFrame:
    long = longitudinal.copy()
    dom = domicilios.copy()
    for base in (long, dom):
        base["codigo_ibge"] = base["codigo_ibge"].astype("string")
        base["ano"] = pd.to_numeric(base["ano"], errors="coerce")
    p10 = long.loc[long["ano"].eq(2010)].set_index("codigo_ibge")
    p22 = long.loc[long["ano"].eq(2022)].set_index("codigo_ibge")
    d10 = dom.loc[dom["ano"].eq(2010)].set_index("codigo_ibge")
    d22 = dom.loc[dom["ano"].eq(2022)].set_index("codigo_ibge")
    codigos = p22.index.intersection(p10.index).intersection(d10.index).intersection(d22.index)
    out = pd.DataFrame(index=codigos)
    out["municipio"] = _limpar_municipio(d22["municipio"].reindex(codigos))
    out["crescimento_pop_2010_2022_pct"] = _crescimento(
        p10["pop_total_harmonizada"].reindex(codigos), p22["pop_total_harmonizada"].reindex(codigos)
    )
    out["crescimento_dpo_2010_2022_pct"] = _crescimento(
        d10["dpo"].reindex(codigos), d22["dpo"].reindex(codigos)
    )
    out["diferenca_dpo_menos_pop_pp"] = (
        out["crescimento_dpo_2010_2022_pct"] - out["crescimento_pop_2010_2022_pct"]
    )
    out = out.reset_index()
    _verificar_30(out, nome="G04")
    return out.sort_values("municipio").reset_index(drop=True)


def plot_g04(dados: pd.DataFrame, destino: Path) -> list[Path]:
    fig, ax = plt.subplots(figsize=FIGSIZE)
    x = dados["crescimento_pop_2010_2022_pct"]
    y = dados["crescimento_dpo_2010_2022_pct"]
    ax.scatter(x, y, s=34)
    minimo = float(np.nanmin([x.min(), y.min()]))
    maximo = float(np.nanmax([x.max(), y.max()]))
    margem = max(2.0, 0.05 * (maximo - minimo))
    lim0, lim1 = minimo - margem, maximo + margem
    ax.plot([lim0, lim1], [lim0, lim1], linewidth=1.0, label="Linha de igualdade")
    ax.set_xlim(lim0, lim1)
    ax.set_ylim(lim0, lim1)
    extremos = dados["diferenca_dpo_menos_pop_pp"].nlargest(4).index.tolist()
    for i in extremos:
        linha = dados.loc[i]
        ax.annotate(
            str(linha["municipio"]),
            (linha["crescimento_pop_2010_2022_pct"], linha["crescimento_dpo_2010_2022_pct"]),
            xytext=(4, 4),
            textcoords="offset points",
            fontsize=7.4,
        )
    ax.set_xlabel("Crescimento populacional 2010–2022 (%)")
    ax.set_ylabel("Crescimento dos domicílios ocupados 2010–2022 (%)")
    ax.legend(frameon=False, loc="upper left")
    ax.spines[["top", "right"]].set_visible(False)
    _rodape(fig, "G04")
    fig.subplots_adjust(top=0.82, bottom=0.20)
    return _salvar(fig, destino, "G04")


def dados_g05(domicilios: pd.DataFrame) -> pd.DataFrame:
    base = domicilios.copy()
    base["codigo_ibge"] = base["codigo_ibge"].astype("string")
    base["ano"] = pd.to_numeric(base["ano"], errors="coerce")
    tab = base.pivot(index="codigo_ibge", columns="ano", values="tam_medio")
    nomes = (
        base.loc[base["ano"].eq(2022), ["codigo_ibge", "municipio"]]
        .drop_duplicates("codigo_ibge")
        .set_index("codigo_ibge")["municipio"]
    )
    out = pd.DataFrame(
        {
            "municipio": _limpar_municipio(nomes.reindex(tab.index)),
            "tam_medio_2000": pd.to_numeric(tab[2000], errors="coerce"),
            "tam_medio_2010": pd.to_numeric(tab[2010], errors="coerce"),
            "tam_medio_2022": pd.to_numeric(tab[2022], errors="coerce"),
        },
        index=tab.index,
    )
    out["variacao_2000_2022"] = out["tam_medio_2022"] - out["tam_medio_2000"]
    out = out.reset_index()
    _verificar_30(out, nome="G05")
    return out.sort_values(["variacao_2000_2022", "municipio"]).reset_index(drop=True)


def plot_g05(dados: pd.DataFrame, destino: Path) -> list[Path]:
    fig, ax = plt.subplots(figsize=FIGSIZE_TALL)
    y = np.arange(len(dados))
    ax.hlines(y, dados["tam_medio_2022"], dados["tam_medio_2000"], linewidth=0.8)
    ax.scatter(dados["tam_medio_2000"], y, s=24, label="2000")
    ax.scatter(dados["tam_medio_2010"], y, s=24, label="2010")
    ax.scatter(dados["tam_medio_2022"], y, s=24, label="2022")
    ax.set_yticks(y, dados["municipio"], fontsize=7.5)
    ax.set_xlabel("Pessoas por domicílio ocupado")
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.02))
    ax.grid(axis="x", linewidth=0.4, alpha=0.35)
    ax.spines[["top", "right", "left"]].set_visible(False)
    _rodape(fig, "G05")
    fig.subplots_adjust(top=0.91, bottom=0.11, left=0.23)
    return _salvar(fig, destino, "G05")


def dados_g06(domicilios: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    base = domicilios.copy()
    base["codigo_ibge"] = base["codigo_ibge"].astype("string")
    base["ano"] = pd.to_numeric(base["ano"], errors="coerce")
    anos = [2000, 2010, 2022]
    regional = []
    for ano in anos:
        sub = base.loc[base["ano"].eq(ano)].copy()
        unip = pd.to_numeric(sub["unipessoais"], errors="coerce").sum(min_count=1)
        den = pd.to_numeric(sub["dpp_num_moradores"], errors="coerce").sum(min_count=1)
        regional.append(
            {
                "ano": ano,
                "unipessoais": int(unip),
                "pct_unipessoais": 100.0 * float(unip) / float(den),
            }
        )
    regio = pd.DataFrame(regional)

    tab = base.pivot(index="codigo_ibge", columns="ano", values="pct_unipessoais")
    nomes = (
        base.loc[base["ano"].eq(2022), ["codigo_ibge", "municipio"]]
        .drop_duplicates("codigo_ibge")
        .set_index("codigo_ibge")["municipio"]
    )
    municipal = pd.DataFrame(
        {
            "municipio": _limpar_municipio(nomes.reindex(tab.index)),
            "pct_unipessoais_2000": 100.0 * pd.to_numeric(tab[2000], errors="coerce"),
            "pct_unipessoais_2010": 100.0 * pd.to_numeric(tab[2010], errors="coerce"),
            "pct_unipessoais_2022": 100.0 * pd.to_numeric(tab[2022], errors="coerce"),
        },
        index=tab.index,
    )
    municipal["variacao_2000_2022_pp"] = municipal["pct_unipessoais_2022"] - municipal["pct_unipessoais_2000"]
    municipal = municipal.reset_index()
    _verificar_30(municipal, nome="G06")
    municipal = municipal.sort_values(["variacao_2000_2022_pp", "municipio"]).reset_index(drop=True)
    return regio, municipal


def plot_g06(regional: pd.DataFrame, municipal: pd.DataFrame, destino: Path) -> list[Path]:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.4, 7.0), gridspec_kw={"width_ratios": [0.78, 1.55]})
    x = np.arange(len(regional))
    ax1.bar(x, regional["unipessoais"])
    ax1.set_xticks(x, regional["ano"].astype(str))
    ax1.set_ylabel("Domicílios unipessoais — total regional")
    for i, linha in regional.iterrows():
        ax1.text(i, linha["unipessoais"], f"{int(linha['unipessoais']):,}".replace(",", "."), ha="center", va="bottom", fontsize=8)
        ax1.text(i, linha["unipessoais"] * 0.91, f"{linha['pct_unipessoais']:.1f}%", ha="center", va="top", fontsize=8)
    ax1.spines[["top", "right"]].set_visible(False)

    y = np.arange(len(municipal))
    ax2.hlines(y, municipal["pct_unipessoais_2000"], municipal["pct_unipessoais_2022"], linewidth=0.8)
    ax2.scatter(municipal["pct_unipessoais_2000"], y, s=20, label="2000")
    ax2.scatter(municipal["pct_unipessoais_2022"], y, s=20, label="2022")
    ax2.set_yticks(y, municipal["municipio"], fontsize=7.2)
    ax2.set_xlabel("Participação de domicílios unipessoais (%)")
    ax2.legend(frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(0.5, 1.02))
    ax2.spines[["top", "right", "left"]].set_visible(False)
    ax2.grid(axis="x", linewidth=0.4, alpha=0.35)
    _rodape(fig, "G06")
    fig.subplots_adjust(top=0.89, bottom=0.11, left=0.08, right=0.98, wspace=0.43)
    return _salvar(fig, destino, "G06")


def _proporcao_regional_de_somas(
    somas: pd.DataFrame, numerador: list[str], denominador: list[str]
) -> tuple[float, float, float]:
    totais = somas.sum(axis=0, min_count=1)
    num = float(totais[numerador].sum(min_count=len(numerador)))
    den = float(totais[denominador].sum(min_count=len(denominador)))
    if den <= 0 or num < 0 or num > den:
        raise ValueError(f"Composição regional inválida: num={num}, den={den}")
    return num, den, num / den


def dados_g09_regional(paths, isau: pd.DataFrame) -> pd.DataFrame:
    from .etapa05c import _arquivo_por_url, _ler_csv_zip, _preparar_setor
    from .etapa10_corrente import BLOCOS_COMPOSICIONAIS, FISICO_SANITARIOS, _selecionar_url, _somas_municipais

    qa05b_path = paths.qa / "etapa05b_inspecao_fontes_isau.json"
    qa05b = json.loads(qa05b_path.read_text(encoding="utf-8"))
    base = isau.copy()
    base["codigo_setor"] = base["codigo_setor"].astype("string").str.strip()
    base["codigo_ibge"] = base["codigo_ibge"].astype("string").str.strip()
    if len(base) != 9087 or base["codigo_setor"].duplicated().any():
        raise AssertionError("G09 exige o universo urbano corrente de 9.087 setores únicos.")
    indice = pd.Index(base["codigo_setor"], name="codigo_setor")
    codigo_ibge_por_setor = base.set_index("codigo_setor")["codigo_ibge"].reindex(indice)

    raw_dom = paths.raw / "ibge" / "censo2022" / "isau" / "domicilios"
    urls = {
        "domicilio1": _selecionar_url(qa05b, "caracteristicas_domicilio1"),
        "domicilio2": _selecionar_url(qa05b, "caracteristicas_domicilio2"),
    }
    fontes = {
        chave: _preparar_setor(
            _ler_csv_zip(_arquivo_por_url(raw_dom, url)), "CD_setor", "CD_SETOR", "setor"
        ).reindex(indice)
        for chave, url in urls.items()
    }
    variaveis = {
        chave: sorted(
            {
                var
                for nome in FISICO_SANITARIOS
                for regra in [BLOCOS_COMPOSICIONAIS[nome]]
                if regra["fonte"] == chave
                for var in regra["denominador"]
            }
        )
        for chave in urls
    }
    somas = {
        chave: _somas_municipais(fontes[chave], codigo_ibge_por_setor, vars_)
        for chave, vars_ in variaveis.items()
    }

    linhas = []
    for nome in FISICO_SANITARIOS:
        regra = BLOCOS_COMPOSICIONAIS[nome]
        tab = somas[str(regra["fonte"])]
        num, den, proporcao = _proporcao_regional_de_somas(
            tab, list(regra["numerador"]), list(regra["denominador"])
        )
        linhas.append(
            {
                "componente": nome,
                "rotulo": G09_ROTULOS[nome],
                "numerador": num,
                "denominador": den,
                "proporcao": proporcao,
                "percentual": 100.0 * proporcao,
            }
        )
    return pd.DataFrame(linhas).sort_values("percentual").reset_index(drop=True)


def plot_g09(dados: pd.DataFrame, destino: Path) -> list[Path]:
    fig, ax = plt.subplots(figsize=FIGSIZE)
    y = np.arange(len(dados))
    ax.barh(y, dados["percentual"])
    ax.set_yticks(y, dados["rotulo"], fontsize=8)
    ax.set_xlabel("Domicílios do universo válido (%)")
    xmax = max(1.0, float(dados["percentual"].max()) * 1.22)
    ax.set_xlim(0, xmax)
    for i, valor in enumerate(dados["percentual"]):
        ax.text(float(valor) + xmax * 0.012, i, f"{float(valor):.2f}%", va="center", fontsize=8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.grid(axis="x", linewidth=0.4, alpha=0.35)
    _rodape(fig, "G09")
    fig.subplots_adjust(top=0.82, bottom=0.18, left=0.34)
    return _salvar(fig, destino, "G09")


def dados_g11(sintese: pd.DataFrame, distributivas: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float | int]]:
    s = sintese.copy()
    d = distributivas.copy()
    for base in (s, d):
        base["codigo_ibge"] = base["codigo_ibge"].astype("string")
    out = s[["codigo_ibge", "municipio", "gravidade_fisico_urbana"]].merge(
        d[["codigo_ibge", "pct_preta_parda_urbano"]], on="codigo_ibge", how="inner", validate="one_to_one"
    )
    out["pct_preta_parda_urbano"] = 100.0 * pd.to_numeric(out["pct_preta_parda_urbano"], errors="coerce")
    _verificar_30(out, nome="G11")
    corr = _spearman(out["pct_preta_parda_urbano"], out["gravidade_fisico_urbana"])
    return out.sort_values("municipio").reset_index(drop=True), corr


def plot_g11(dados: pd.DataFrame, corr: dict[str, float | int], destino: Path) -> list[Path]:
    fig, ax = plt.subplots(figsize=FIGSIZE)
    x = dados["pct_preta_parda_urbano"]
    y = dados["gravidade_fisico_urbana"]
    ax.scatter(x, y, s=34)
    for i in _selecionar_rotulos_extremos(dados, "pct_preta_parda_urbano", "gravidade_fisico_urbana"):
        linha = dados.loc[i]
        ax.annotate(str(linha["municipio"]), (linha["pct_preta_parda_urbano"], linha["gravidade_fisico_urbana"]), xytext=(4, 4), textcoords="offset points", fontsize=7.3)
    ax.set_xlabel("População preta e parda na população urbana válida (%)")
    ax.set_ylabel("Gravidade físico-urbana — índice relativo (0–1)")
    ax.set_ylim(0, 1)
    ax.spines[["top", "right"]].set_visible(False)
    extra = f"Spearman: ρ={float(corr['rho']):.2f}; p={float(corr['p_valor']):.3g}; n={int(corr['n'])}."
    _rodape(fig, "G11", extra=extra)
    fig.subplots_adjust(top=0.82, bottom=0.21)
    return _salvar(fig, destino, "G11")


def dados_g12(sintese: pd.DataFrame) -> pd.DataFrame:
    out = sintese[["codigo_ibge", "municipio", "gravidade_fisico_sanitaria", "gravidade_entorno"]].copy()
    out["codigo_ibge"] = out["codigo_ibge"].astype("string")
    _verificar_30(out, nome="G12")
    return out.sort_values("municipio").reset_index(drop=True)


def plot_g12(dados: pd.DataFrame, destino: Path) -> list[Path]:
    fig, ax = plt.subplots(figsize=FIGSIZE)
    ax.scatter(dados["gravidade_fisico_sanitaria"], dados["gravidade_entorno"], s=30)
    destaques = {"Sumaré", "Várzea Paulista", "Nova Odessa"}
    sub = dados.loc[dados["municipio"].isin(destaques)]
    ax.scatter(sub["gravidade_fisico_sanitaria"], sub["gravidade_entorno"], s=48)
    for _, linha in sub.iterrows():
        ax.annotate(str(linha["municipio"]), (linha["gravidade_fisico_sanitaria"], linha["gravidade_entorno"]), xytext=(5, 5), textcoords="offset points", fontsize=8)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Gravidade físico-sanitária — índice relativo (0–1)")
    ax.set_ylabel("Carências do entorno — índice relativo (0–1)")
    ax.spines[["top", "right"]].set_visible(False)
    _rodape(fig, "G12")
    fig.subplots_adjust(top=0.82, bottom=0.20)
    return _salvar(fig, destino, "G12")


def dados_g13(sintese: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float | int]]:
    out = sintese[["codigo_ibge", "municipio", "crescimento_dpo_2010_2022", "gravidade_fisico_urbana"]].copy()
    out["codigo_ibge"] = out["codigo_ibge"].astype("string")
    out["crescimento_dpo_2010_2022_pct"] = 100.0 * pd.to_numeric(
        out["crescimento_dpo_2010_2022"], errors="coerce"
    )
    out = out.drop(columns="crescimento_dpo_2010_2022")
    _verificar_30(out, nome="G13")
    corr = _spearman(out["crescimento_dpo_2010_2022_pct"], out["gravidade_fisico_urbana"])
    return out.sort_values("municipio").reset_index(drop=True), corr


def plot_g13(dados: pd.DataFrame, corr: dict[str, float | int], destino: Path) -> list[Path]:
    fig, ax = plt.subplots(figsize=FIGSIZE)
    ax.scatter(dados["crescimento_dpo_2010_2022_pct"], dados["gravidade_fisico_urbana"], s=34)
    for i in _selecionar_rotulos_extremos(dados, "crescimento_dpo_2010_2022_pct", "gravidade_fisico_urbana"):
        linha = dados.loc[i]
        ax.annotate(str(linha["municipio"]), (linha["crescimento_dpo_2010_2022_pct"], linha["gravidade_fisico_urbana"]), xytext=(4, 4), textcoords="offset points", fontsize=7.3)
    ax.set_xlabel("Crescimento dos domicílios ocupados 2010–2022 (%)")
    ax.set_ylabel("Gravidade físico-urbana — índice relativo (0–1)")
    ax.set_ylim(0, 1)
    ax.spines[["top", "right"]].set_visible(False)
    extra = f"Spearman: ρ={float(corr['rho']):.2f}; p={float(corr['p_valor']):.2f}; n={int(corr['n'])}."
    _rodape(fig, "G13", extra=extra)
    fig.subplots_adjust(top=0.82, bottom=0.21)
    return _salvar(fig, destino, "G13")


def _registrar_saidas(
    manifesto: Path,
    registrar_arquivo,
    arquivos: Iterable[Path],
    *,
    origem: str,
    data_root: Path,
) -> list[str]:
    saidas = []
    for path in arquivos:
        registrar_arquivo(manifesto, path, origem=origem)
        saidas.append(str(path.relative_to(data_root)))
    return saidas


def executar(raiz: Path) -> None:
    from .paths import resolve_paths
    from .proveniencia import registrar_arquivo, registrar_evento

    raiz = raiz.resolve()
    paths = resolve_paths(raiz)
    paths.create()
    manifesto = paths.manifests / "execucao.jsonl"
    arquivos = {
        "longitudinal": paths.processed / "municipal" / "base_longitudinal_2000_2010_2022.parquet",
        "domicilios": paths.processed / "municipal" / "base_domiciliar_2000_2010_2022.parquet",
        "sintese": paths.processed / "municipal" / "base_sintese_municipal_2022.parquet",
        "distributivas": paths.processed / "municipal" / "base_camadas_distributivas_2022.parquet",
        "isau": paths.processed / "setorial" / "base_isau_2022.parquet",
    }
    for nome, path in arquivos.items():
        if not path.exists():
            raise FileNotFoundError(f"Pré-requisito 11b ausente ({nome}): {path}")
    dados = {nome: pd.read_parquet(path) for nome, path in arquivos.items()}

    graficos_dir = paths.outputs / "graphs"
    dados_dir = paths.output_data / "etapa11b"
    graficos_dir.mkdir(parents=True, exist_ok=True)
    dados_dir.mkdir(parents=True, exist_ok=True)

    qa_graficos: dict[str, dict] = {}

    g02 = dados_g02(dados["longitudinal"])
    g03 = dados_g03(dados["longitudinal"])
    g04 = dados_g04(dados["longitudinal"], dados["domicilios"])
    g05 = dados_g05(dados["domicilios"])
    g06_reg, g06_mun = dados_g06(dados["domicilios"])
    g09 = dados_g09_regional(paths, dados["isau"])
    g11, corr11 = dados_g11(dados["sintese"], dados["distributivas"])
    g12 = dados_g12(dados["sintese"])
    g13, corr13 = dados_g13(dados["sintese"])

    bases = {
        "G02": [g02],
        "G03": [g03],
        "G04": [g04],
        "G05": [g05],
        "G06": [g06_reg, g06_mun],
        "G09": [g09],
        "G11": [g11],
        "G12": [g12],
        "G13": [g13],
    }
    nomes_bases = {
        "G06": ["G06_regional", "G06_municipios"],
    }
    for codigo, frames in bases.items():
        csvs = []
        for j, frame in enumerate(frames):
            nome = nomes_bases.get(codigo, [codigo] * len(frames))[j]
            path = dados_dir / f"{nome}_dados.csv"
            frame.to_csv(path, index=False, encoding="utf-8")
            registrar_arquivo(manifesto, path, origem=f"Etapa 11b — base pública {codigo}")
            csvs.append(str(path.relative_to(paths.data_root)))
        qa_graficos[codigo] = {"bases_csv": csvs}

    render = {
        "G02": plot_g02(g02, graficos_dir),
        "G03": plot_g03(g03, graficos_dir),
        "G04": plot_g04(g04, graficos_dir),
        "G05": plot_g05(g05, graficos_dir),
        "G06": plot_g06(g06_reg, g06_mun, graficos_dir),
        "G09": plot_g09(g09, graficos_dir),
        "G11": plot_g11(g11, corr11, graficos_dir),
        "G12": plot_g12(g12, graficos_dir),
        "G13": plot_g13(g13, corr13, graficos_dir),
    }
    for codigo, paths_render in render.items():
        qa_graficos[codigo]["arquivos"] = _registrar_saidas(
            manifesto,
            registrar_arquivo,
            paths_render,
            origem=f"Etapa 11b — gráfico {codigo}",
            data_root=paths.data_root,
        )
        qa_graficos[codigo]["titulo"] = TITULOS[codigo]
        qa_graficos[codigo]["fonte"] = FONTES[codigo]
        qa_graficos[codigo]["nota"] = NOTAS[codigo]

    qa = {
        "status": "OK_EDICAO_CORRENTE",
        "etapa": "11b",
        "graficos_gerados": sorted(render),
        "n_graficos": int(len(render)),
        "formatos": ["png", "svg"],
        "checks": {
            "G02_anos": g02["ano"].astype(int).tolist(),
            "G02_pct_soma_100": bool(np.allclose(g02[["pct_0_14", "pct_15_59", "pct_60_mais"]].sum(axis=1), 100.0)),
            "G04_municipios_dpo_cresce_mais_que_pop": int(g04["diferenca_dpo_menos_pop_pp"].gt(0).sum()),
            "G05_municipios_reducao_tamanho_medio": int(g05["variacao_2000_2022"].lt(0).sum()),
            "G06_municipios_aumento_unipessoais": int(g06_mun["variacao_2000_2022_pp"].gt(0).sum()),
            "G09_componentes": int(len(g09)),
            "G11_spearman": corr11,
            "G12_destaques_presentes": sorted(set(g12["municipio"]) & {"Sumaré", "Várzea Paulista", "Nova Odessa"}),
            "G13_spearman": corr13,
        },
        "referencias_historicas_descritivas": {
            "G11_rho": 0.76,
            "G13_rho": -0.04,
            "G13_p": 0.82,
        },
        "regra": "referências históricas servem como QA e não como alvos de calibração; gráficos usam a edição corrente",
        "graficos": qa_graficos,
    }
    qa_path = paths.qa / "etapa11b_graficos.json"
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    registrar_arquivo(manifesto, qa_path, origem="Etapa 11b — QA gráficos")
    registrar_evento(
        manifesto,
        {"tipo": "etapa", "etapa": "11b", "status": qa["status"], "graficos": len(render)},
    )
    print(json.dumps(qa, ensure_ascii=False, indent=2))
