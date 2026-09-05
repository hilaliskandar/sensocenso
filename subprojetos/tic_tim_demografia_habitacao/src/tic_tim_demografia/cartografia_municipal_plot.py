from __future__ import annotations

import textwrap
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "tic-tim-demografia-etapa11c"
matplotlib.rcParams["font.family"] = "DejaVu Sans"
from matplotlib import pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

from .cartografia_municipal_dados import FAMILIAS_PUBLICAS, classificar_quantis

DPI = 220
FIGSIZE = (10.8, 7.6)
TITULOS = {
    "M01": "Crescimento populacional entre 2010 e 2022",
    "M02": "Envelhecimento da população em 2022",
    "M03": "Renovação geracional em 2022",
    "M05": "Participação da população preta e parda na população urbana com informação válida de cor ou raça",
    "M10": "Domicílios com abastecimento de água fora da rede geral",
    "M11": "Domicílios com esgotamento sanitário inadequado",
    "M14": "Panorama regional das dimensões predominantes",
}
FONTES = {
    "M01": "Elaborado a partir de IBGE, Censos Demográficos 2010 e 2022.",
    "M02": "Elaborado a partir de IBGE, Censo Demográfico 2022.",
    "M03": "Elaborado a partir de IBGE, Censo Demográfico 2022.",
    "M05": "Elaborado a partir de IBGE, Censo Demográfico 2022.",
    "M10": "Elaborado a partir de IBGE, Censo Demográfico 2022.",
    "M11": "Elaborado a partir de IBGE, Censo Demográfico 2022.",
    "M14": "Elaboração própria a partir de IBGE, Censos Demográficos 2010 e 2022.",
}
NOTAS = {
    "M01": "Unidade em %. Municípios com redução populacional são hachurados.",
    "M02": "Razão de pessoas de 60 anos ou mais por 100 crianças de 0–14 anos.",
    "M03": "Proxy censitária: crianças de 0–4 anos por mil mulheres de 15–49 anos.",
    "M05": "Percentual calculado no universo urbano com informação válida de cor ou raça.",
    "M10": "Percentual de domicílios do universo urbano de referência; abastecimento fora da rede geral é distinto de ausência de água.",
    "M11": "Percentual de domicílios do universo urbano de referência; categorias preservam a correspondência com o IBGE.",
    "M14": "Categorias não ordinais. Predominância pela maior incidência municipal entre as quatro famílias; empates preservados.",
}
UNIDADES = {"M01": "%", "M02": "pessoas 60+ / 100 crianças", "M03": "por mil", "M05": "%", "M10": "%", "M11": "%"}


def _escala(ax: plt.Axes, gdf: gpd.GeoDataFrame) -> None:
    minx, miny, maxx, maxy = gdf.total_bounds
    largura, altura = maxx - minx, maxy - miny
    opcoes = np.asarray([5_000, 10_000, 20_000, 25_000, 50_000, 100_000], dtype=float)
    cand = opcoes[opcoes <= largura * 0.25]
    comp = float(cand[-1] if len(cand) else opcoes[0])
    x0, y0 = minx + 0.05 * largura, miny + 0.06 * altura
    tick = min(1_000.0, 0.012 * altura)
    ax.plot([x0, x0 + comp], [y0, y0], color="black", linewidth=2)
    for x in (x0, x0 + comp):
        ax.plot([x, x], [y0 - tick, y0 + tick], color="black", linewidth=1)
    ax.text(x0 + comp / 2, y0 + 1.8 * tick, f"{comp / 1000:g} km", ha="center", fontsize=8)


def _norte(ax: plt.Axes, gdf: gpd.GeoDataFrame) -> None:
    minx, miny, maxx, maxy = gdf.total_bounds
    largura, altura = maxx - minx, maxy - miny
    x, y = maxx - 0.06 * largura, maxy - 0.07 * altura
    ax.annotate("", xy=(x, y + .04 * altura), xytext=(x, y - .02 * altura), arrowprops={"arrowstyle": "-|>", "linewidth": 1.2})
    ax.text(x, y + .045 * altura, "N", ha="center", va="bottom", fontsize=9, fontweight="bold")


def _titulo(fig: plt.Figure, codigo: str) -> None:
    fig.text(.05, .955, textwrap.fill(TITULOS[codigo], 78), ha="left", va="top", fontsize=13.2, fontweight="bold")


def _rodape(fig: plt.Figure, codigo: str) -> None:
    fig.text(.05, .065, f"Fonte: {FONTES[codigo]}", ha="left", fontsize=8.2)
    fig.text(.05, .043, f"Nota: {NOTAS[codigo]}", ha="left", fontsize=7.9)
    fig.text(.05, .020, "Referência cartográfica: limites municipais derivados da malha de setores censitários 2022 do IBGE; SIRGAS 2000 / UTM 23S (EPSG:31983).", ha="left", fontsize=7.5)


def _salvar(fig: plt.Figure, destino: Path, codigo: str) -> list[Path]:
    destino.mkdir(parents=True, exist_ok=True)
    png, svg = destino / f"{codigo}.png", destino / f"{codigo}.svg"
    fig.savefig(png, dpi=DPI, bbox_inches="tight", metadata={"Software": "tic_tim_demografia_etapa11c"})
    fig.savefig(svg, bbox_inches="tight", metadata={"Date": None, "Creator": "tic_tim_demografia_etapa11c"})
    plt.close(fig)
    return [png, svg]


def plot_continuo(gdf: gpd.GeoDataFrame, codigo: str, destino: Path) -> tuple[list[Path], dict[str, object]]:
    mapa = gdf.copy()
    classes, bins, rotulos = classificar_quantis(mapa[codigo])
    mapa[f"classe_{codigo}"] = classes
    fig = plt.figure(figsize=FIGSIZE)
    ax, lateral = fig.add_axes([.05, .14, .68, .75]), fig.add_axes([.76, .15, .21, .69])
    lateral.axis("off")
    cmap = plt.get_cmap("viridis", len(rotulos))
    cores = {r: cmap(i) for i, r in enumerate(rotulos)}
    for r in rotulos:
        sub = mapa.loc[mapa[f"classe_{codigo}"].eq(r)]
        if not sub.empty:
            sub.plot(ax=ax, color=cores[r], edgecolor="white", linewidth=.7)
    ausentes = mapa.loc[mapa[codigo].isna()]
    if not ausentes.empty:
        ausentes.plot(ax=ax, color="0.85", edgecolor="white", linewidth=.7, hatch="///")
    if codigo == "M01":
        negativos = mapa.loc[pd.to_numeric(mapa[codigo], errors="coerce").lt(0)]
        if not negativos.empty:
            negativos.plot(ax=ax, facecolor="none", edgecolor="black", linewidth=.6, hatch="///")
    mapa.boundary.plot(ax=ax, color=".25", linewidth=.55)
    ax.set_axis_off(); ax.set_aspect("equal"); _escala(ax, mapa); _norte(ax, mapa); _titulo(fig, codigo)
    lateral.text(0, 1, f"Classes ({UNIDADES[codigo]})", va="top", fontsize=10, fontweight="bold")
    handles = [Patch(facecolor=cores[r], edgecolor=".4", label=r) for r in rotulos]
    if codigo == "M01":
        handles.append(Patch(facecolor="white", edgecolor="black", hatch="///", label="Redução populacional (<0%)"))
    handles.append(Patch(facecolor=".85", edgecolor=".5", hatch="///", label="Sem informação"))
    lateral.legend(handles=handles, loc="upper left", bbox_to_anchor=(-.03, .92), frameon=False, fontsize=8.2)
    valores = pd.to_numeric(mapa[codigo], errors="coerce")
    validos = mapa.loc[valores.notna(), ["municipio", codigo]].copy(); validos["_valor"] = pd.to_numeric(validos[codigo], errors="coerce")
    imin, imax, med = validos["_valor"].idxmin(), validos["_valor"].idxmax(), float(validos["_valor"].median())
    lateral.text(0, .46, "Resumo", fontweight="bold", fontsize=10)
    lateral.text(0, .41, f"Mínimo: {validos.loc[imin, 'municipio']}\n{validos.loc[imin, '_valor']:.1f} {UNIDADES[codigo]}\n\nMediana: {med:.1f} {UNIDADES[codigo]}\n\nMáximo: {validos.loc[imax, 'municipio']}\n{validos.loc[imax, '_valor']:.1f} {UNIDADES[codigo]}", va="top", fontsize=8.3)
    lateral.text(0, .05, "Classificação por quintis entre\nos 30 municípios com valor válido.\nLimites registrados no QA.", fontsize=7.6, va="bottom")
    _rodape(fig, codigo)
    return _salvar(fig, destino, codigo), {"unidade": UNIDADES[codigo], "metodo_classes": "quintis_municipais_valores_validos", "limites_classes": bins, "rotulos_classes": rotulos, "n_validos": int(valores.notna().sum()), "n_ausentes": int(valores.isna().sum()), "min": float(valores.min()), "mediana": med, "max": float(valores.max())}


def plot_m14(gdf: gpd.GeoDataFrame, destino: Path) -> tuple[list[Path], dict[str, object]]:
    mapa = gdf.copy(); categorias = sorted(mapa["M14"].dropna().astype(str).unique())
    cmap = plt.get_cmap("tab10"); cores = {"F1": cmap(0), "F2": cmap(2), "F3": cmap(1), "F4": cmap(4)}
    def cor(cat: str):
        rgb = np.asarray([cores[f][:3] for f in cat.split("+")]).mean(axis=0)
        return (*map(float, rgb), 1.0)
    fig = plt.figure(figsize=FIGSIZE); ax = fig.add_axes([.05, .14, .68, .75]); lateral = fig.add_axes([.76, .12, .22, .74]); lateral.axis("off")
    for cat in categorias:
        mapa.loc[mapa["M14"].astype("string").eq(cat)].plot(ax=ax, color=cor(cat), edgecolor="white", linewidth=.7, hatch="//" if "+" in cat else None)
    ausentes = mapa.loc[mapa["M14"].isna()]
    if not ausentes.empty: ausentes.plot(ax=ax, color=".85", edgecolor="white", linewidth=.7, hatch="///")
    mapa.boundary.plot(ax=ax, color=".25", linewidth=.55)
    for (_, linha), p in zip(mapa.iterrows(), mapa.geometry.representative_point(), strict=True):
        if pd.notna(linha["M14"]): ax.text(p.x, p.y, str(linha["M14"]), ha="center", va="center", fontsize=5.4, fontweight="bold")
    ax.set_axis_off(); ax.set_aspect("equal"); _escala(ax, mapa); _norte(ax, mapa); _titulo(fig, "M14")
    lateral.text(0, 1, "Dimensões", fontweight="bold", fontsize=10, va="top"); y=.94
    for f, rot in FAMILIAS_PUBLICAS.items():
        lateral.add_patch(plt.Rectangle((0, y-.018), .08, .028, transform=lateral.transAxes, facecolor=cores[f], edgecolor=".4"))
        lateral.text(.11, y, f"{f} — {rot}", transform=lateral.transAxes, fontsize=7.5, va="center", wrap=True); y -= .105
    empates = mapa.loc[mapa["M14"].astype("string").str.contains("+", regex=False, na=False)]
    lateral.text(0, y, "Empates", fontweight="bold", fontsize=9, transform=lateral.transAxes); y -= .05
    if empates.empty: lateral.text(0, y, "Nenhum empate.", fontsize=7.8, transform=lateral.transAxes)
    else:
        for cat, n in empates["M14"].value_counts().sort_index().items():
            lateral.text(0, y, f"{cat}: {int(n)} município(s)", fontsize=7.8, transform=lateral.transAxes); y -= .04
    lateral.text(0, .17, "O código da dimensão predominante\né impresso em cada município.\nCategorias não são ordinais.", fontsize=7.6, transform=lateral.transAxes, va="top")
    _rodape(fig, "M14")
    cont = mapa["M14"].value_counts(dropna=False).to_dict()
    return _salvar(fig, destino, "M14"), {"categorias": {str(k): int(v) for k, v in cont.items()}, "n_empates": int(len(empates)), "familias_publicas": FAMILIAS_PUBLICAS, "regra_predominancia": "maior percentual de setores com sinal entre observados de cada família; empates preservados"}
