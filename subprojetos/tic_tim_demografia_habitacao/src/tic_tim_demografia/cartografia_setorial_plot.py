from __future__ import annotations

import textwrap
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "tic-tim-demografia-etapa11d"
matplotlib.rcParams["font.family"] = "DejaVu Sans"
from matplotlib import pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

from .cartografia_setorial_dados import (
    M12_COMPONENTES,
    InsetSelecao,
    categorizar_m08,
    categorizar_m09,
    classificar_quantis_setoriais,
    classificar_zero_mais_quantis,
)

DPI = 220
FIGSIZE = (11.6, 8.1)
TITULOS = {
    "M04": "Renovação geracional em escala local",
    "M06": "Privação sanitário-ambiental associada à moradia",
    "M08": "Áreas com necessidades habitacionais combinadas",
    "M09": "Estabilidade das áreas de necessidades combinadas sob critério mais restritivo",
    "M12": "Principais carências da infraestrutura do entorno urbano",
}
FONTES = {
    "M04": "Elaborado a partir de IBGE, Censo Demográfico 2022.",
    "M06": "Elaborado a partir de IBGE, Censo Demográfico 2022.",
    "M08": "Elaborado a partir de IBGE, Censo Demográfico 2022.",
    "M09": "Elaborado a partir de IBGE, Censo Demográfico 2022.",
    "M12": "Elaborado a partir de IBGE, Censo Demográfico 2022, Pesquisa Urbanística do Entorno dos Domicílios — moradores.",
}


def _escala(
    ax: plt.Axes,
    gdf: gpd.GeoDataFrame,
    *,
    x_frac: float = 0.04,
    y_frac: float = 0.045,
    label_above: bool = True,
) -> None:
    minx, miny, maxx, maxy = gdf.total_bounds
    largura, altura = maxx - minx, maxy - miny
    opcoes = np.asarray([5_000, 10_000, 20_000, 25_000, 50_000, 100_000], dtype=float)
    candidatas = opcoes[opcoes <= largura * 0.25]
    comp = float(candidatas[-1] if len(candidatas) else opcoes[0])
    x0, y0 = minx + x_frac * largura, miny + y_frac * altura
    tick = min(1_000.0, 0.012 * altura)
    ax.plot([x0, x0 + comp], [y0, y0], color="black", linewidth=1.8, zorder=20)
    for x in (x0, x0 + comp):
        ax.plot([x, x], [y0 - tick, y0 + tick], color="black", linewidth=1, zorder=20)
    dy = 1.8 * tick if label_above else -3.0 * tick
    ax.text(
        x0 + comp / 2,
        y0 + dy,
        f"{comp / 1000:g} km",
        ha="center",
        va="bottom" if label_above else "top",
        fontsize=7.6,
        zorder=20,
    )


def _norte(ax: plt.Axes, gdf: gpd.GeoDataFrame) -> None:
    minx, miny, maxx, maxy = gdf.total_bounds
    largura, altura = maxx - minx, maxy - miny
    x, y = maxx - 0.055 * largura, maxy - 0.07 * altura
    ax.annotate(
        "",
        xy=(x, y + 0.04 * altura),
        xytext=(x, y - 0.02 * altura),
        arrowprops={"arrowstyle": "-|>", "linewidth": 1.1},
        zorder=20,
    )
    ax.text(
        x,
        y + 0.045 * altura,
        "N",
        ha="center",
        va="bottom",
        fontsize=8.5,
        fontweight="bold",
        zorder=20,
    )


def _titulo(fig: plt.Figure, codigo: str) -> None:
    fig.text(
        0.045,
        0.965,
        textwrap.fill(TITULOS[codigo], 92),
        ha="left",
        va="top",
        fontsize=13.0,
        fontweight="bold",
    )


def _rodape(fig: plt.Figure, codigo: str, nota: str) -> None:
    fig.text(0.045, 0.056, f"Fonte: {FONTES[codigo]}", ha="left", fontsize=7.8)
    fig.text(0.045, 0.035, f"Nota: {nota}", ha="left", fontsize=7.55)
    fig.text(
        0.045,
        0.014,
        "Referência cartográfica: malha de setores censitários 2022 do IBGE; SIRGAS 2000 / UTM 23S (EPSG:31983).",
        ha="left",
        fontsize=7.2,
    )


def _salvar(fig: plt.Figure, destino: Path, codigo: str) -> list[Path]:
    destino.mkdir(parents=True, exist_ok=True)
    png = destino / f"{codigo}.png"
    svg = destino / f"{codigo}.svg"
    fig.savefig(
        png,
        dpi=DPI,
        bbox_inches="tight",
        metadata={"Software": "tic_tim_demografia_etapa11d"},
    )
    fig.savefig(
        svg,
        bbox_inches="tight",
        metadata={"Date": None, "Creator": "tic_tim_demografia_etapa11d"},
    )
    plt.close(fig)
    return [png, svg]


def _base_region(ax: plt.Axes, limites: gpd.GeoDataFrame) -> None:
    limites.plot(ax=ax, facecolor="0.965", edgecolor="0.45", linewidth=0.65, zorder=0)


def _limites_region(ax: plt.Axes, limites: gpd.GeoDataFrame) -> None:
    limites.boundary.plot(ax=ax, color="0.24", linewidth=0.62, zorder=12)


def _plot_classes(
    ax: plt.Axes,
    setores: gpd.GeoDataFrame,
    classe_col: str,
    rotulos: list[str],
    cores: dict[str, object],
    *,
    edgecolor: str | None = None,
    linewidth: float = 0.0,
) -> None:
    for rotulo in rotulos:
        sub = setores.loc[setores[classe_col].eq(rotulo)]
        if not sub.empty:
            sub.plot(
                ax=ax,
                color=cores[rotulo],
                edgecolor=edgecolor,
                linewidth=linewidth,
                zorder=3,
            )


def _sidebar_legend(
    fig: plt.Figure,
    handles: list[Patch],
    titulo: str,
    *,
    altura: float = 0.18,
) -> None:
    ax = fig.add_axes([0.70, 0.72, 0.28, altura])
    ax.axis("off")
    ax.legend(
        handles=handles,
        title=titulo,
        loc="upper left",
        frameon=False,
        fontsize=7.8,
        title_fontsize=8.8,
        borderaxespad=0,
    )


def _inset_axes(fig: plt.Figure, posicao: float) -> plt.Axes:
    return fig.add_axes([0.71, posicao, 0.255, 0.16])


def plot_continuo_com_insets(
    setores: gpd.GeoDataFrame,
    limites: gpd.GeoDataFrame,
    *,
    codigo: str,
    coluna: str,
    insets: list[InsetSelecao],
    destino: Path,
    unidade: str,
    casas: int,
    nota: str,
) -> tuple[list[Path], dict[str, object]]:
    mapa = setores.copy()
    classes, bins, rotulos = classificar_quantis_setoriais(
        mapa[coluna], n_classes=5, casas=casas
    )
    mapa["_classe"] = classes
    cmap = plt.get_cmap("viridis", len(rotulos))
    cores = {rotulo: cmap(i) for i, rotulo in enumerate(rotulos)}
    fig = plt.figure(figsize=FIGSIZE)
    ax = fig.add_axes([0.045, 0.13, 0.64, 0.77])
    _base_region(ax, limites)
    _plot_classes(ax, mapa, "_classe", rotulos, cores)
    ausentes = mapa.loc[pd.to_numeric(mapa[coluna], errors="coerce").isna()]
    if not ausentes.empty:
        ausentes.plot(ax=ax, color="0.82", edgecolor="none", zorder=2)
    _limites_region(ax, limites)
    ax.set_axis_off()
    ax.set_aspect("equal")
    _escala(ax, limites)
    _norte(ax, limites)
    _titulo(fig, codigo)

    handles = [Patch(facecolor=cores[r], edgecolor="0.45", label=r) for r in rotulos]
    handles.append(Patch(facecolor="0.82", edgecolor="0.5", label="Sem informação"))
    _sidebar_legend(fig, handles, f"Classes ({unidade})")

    insets_qa: list[dict[str, object]] = []
    for sel, y in zip(insets, [0.50, 0.30, 0.10], strict=False):
        axi = _inset_axes(fig, y)
        lim = limites.loc[limites["codigo_ibge"].astype(str).eq(sel.codigo_ibge)]
        sub = mapa.loc[mapa["codigo_ibge"].astype(str).eq(sel.codigo_ibge)]
        if lim.empty or sub.empty:
            raise AssertionError(f"Inset {codigo} sem geometria/dados: {sel.codigo_ibge}")
        _base_region(axi, lim)
        _plot_classes(
            axi,
            sub,
            "_classe",
            rotulos,
            cores,
            edgecolor="white",
            linewidth=0.12,
        )
        subaus = sub.loc[pd.to_numeric(sub[coluna], errors="coerce").isna()]
        if not subaus.empty:
            subaus.plot(ax=axi, color="0.82", edgecolor="white", linewidth=0.12)
        lim.boundary.plot(ax=axi, color="0.2", linewidth=0.75)
        axi.set_axis_off()
        axi.set_aspect("equal")
        axi.set_title(sel.municipio, fontsize=8.2, fontweight="bold", pad=1.5)
        insets_qa.append(
            {
                "codigo_ibge": sel.codigo_ibge,
                "municipio": sel.municipio,
                "metrica_selecao": sel.metrica,
            }
        )

    valores = pd.to_numeric(mapa[coluna], errors="coerce")
    _rodape(fig, codigo, nota)
    qa = {
        "universo_setorial": int(len(mapa)),
        "n_validos": int(valores.notna().sum()),
        "n_ausentes": int(valores.isna().sum()),
        "metodo_classes": "quintis_setoriais_valores_validos",
        "limites_classes": bins,
        "rotulos_classes": rotulos,
        "unidade": unidade,
        "min": float(valores.min()),
        "mediana": float(valores.median()),
        "max": float(valores.max()),
        "insets": insets_qa,
    }
    return _salvar(fig, destino, codigo), qa


def plot_m08(
    setores: gpd.GeoDataFrame,
    limites: gpd.GeoDataFrame,
    insets: list[InsetSelecao],
    destino: Path,
    *,
    referencia_historica: int = 1255,
) -> tuple[list[Path], dict[str, object]]:
    mapa = setores.copy()
    mapa["_categoria"] = categorizar_m08(mapa)
    ordem = [
        "0–2 dimensões",
        "Classificação indeterminada",
        "3 dimensões",
        "4 dimensões",
    ]
    cores = {
        "0–2 dimensões": "#eeeeee",
        "Classificação indeterminada": "white",
        "3 dimensões": "#f28e2b",
        "4 dimensões": "#9c2f2f",
    }
    fig = plt.figure(figsize=FIGSIZE)
    ax = fig.add_axes([0.045, 0.13, 0.64, 0.77])
    _base_region(ax, limites)
    for categoria in ordem:
        sub = mapa.loc[mapa["_categoria"].eq(categoria)]
        if not sub.empty:
            sub.plot(
                ax=ax,
                color=cores[categoria],
                edgecolor="none",
                hatch="///" if categoria == "Classificação indeterminada" else None,
                zorder=3,
            )
    _limites_region(ax, limites)
    ax.set_axis_off()
    ax.set_aspect("equal")
    _escala(ax, limites)
    _norte(ax, limites)
    _titulo(fig, "M08")
    handles = [
        Patch(
            facecolor=cores[c],
            edgecolor="0.5",
            hatch="///" if c == "Classificação indeterminada" else None,
            label=c,
        )
        for c in ordem
    ]
    _sidebar_legend(fig, handles, "Coexistência de dimensões", altura=0.15)

    insets_qa: list[dict[str, object]] = []
    for sel, y in zip(insets, [0.50, 0.30, 0.10], strict=False):
        axi = _inset_axes(fig, y)
        lim = limites.loc[limites["codigo_ibge"].astype(str).eq(sel.codigo_ibge)]
        sub = mapa.loc[mapa["codigo_ibge"].astype(str).eq(sel.codigo_ibge)]
        if lim.empty or sub.empty:
            raise AssertionError(f"Inset M08 sem geometria/dados: {sel.codigo_ibge}")
        _base_region(axi, lim)
        for categoria in ordem:
            s = sub.loc[sub["_categoria"].eq(categoria)]
            if not s.empty:
                s.plot(
                    ax=axi,
                    color=cores[categoria],
                    edgecolor="white",
                    linewidth=0.10,
                    hatch="///" if categoria == "Classificação indeterminada" else None,
                )
        lim.boundary.plot(ax=axi, color="0.2", linewidth=0.75)
        axi.set_axis_off()
        axi.set_aspect("equal")
        axi.set_title(sel.municipio, fontsize=8.2, fontweight="bold", pad=1.5)
        insets_qa.append(
            {
                "codigo_ibge": sel.codigo_ibge,
                "municipio": sel.municipio,
                "pct_convergentes": sel.metrica,
            }
        )

    contagens = mapa["_categoria"].value_counts().to_dict()
    corrente = int(contagens.get("3 dimensões", 0) + contagens.get("4 dimensões", 0))
    nota = (
        f"Critério relativo P75; edição corrente: {corrente:,} setores com 3 ou 4 dimensões "
        f"(3D={int(contagens.get('3 dimensões', 0)):,}; 4D={int(contagens.get('4 dimensões', 0)):,}). "
        f"Referência histórica: {referencia_historica:,}. Não representa prioridade normativa."
    ).replace(",", ".")
    _rodape(fig, "M08", nota)
    qa = {
        "universo_setorial": int(len(mapa)),
        "categorias": {str(k): int(v) for k, v in contagens.items()},
        "convergentes_correntes": corrente,
        "referencia_historica": int(referencia_historica),
        "delta": corrente - int(referencia_historica),
        "insets": insets_qa,
    }
    return _salvar(fig, destino, "M08"), qa


def plot_m09(
    setores: gpd.GeoDataFrame,
    limites: gpd.GeoDataFrame,
    destino: Path,
    *,
    referencia_persistentes: int = 959,
) -> tuple[list[Path], dict[str, object]]:
    mapa = setores.copy()
    mapa["_categoria"] = categorizar_m09(mapa)
    ordem = [
        "Fora do critério P75",
        "P75 indeterminado",
        "P75, P80 indeterminado",
        "P75, não persistente no P80",
        "Persistente, composição alterada",
        "Persistente, mesmo vetor",
    ]
    cores = {
        "Fora do critério P75": "#eeeeee",
        "P75 indeterminado": "white",
        "P75, P80 indeterminado": "#fff4d6",
        "P75, não persistente no P80": "#f3c969",
        "Persistente, composição alterada": "#e07a3f",
        "Persistente, mesmo vetor": "#35618d",
    }
    fig = plt.figure(figsize=FIGSIZE)
    ax = fig.add_axes([0.045, 0.13, 0.69, 0.77])
    side = fig.add_axes([0.76, 0.15, 0.22, 0.70])
    side.axis("off")
    _base_region(ax, limites)
    for categoria in ordem:
        sub = mapa.loc[mapa["_categoria"].eq(categoria)]
        if not sub.empty:
            sub.plot(
                ax=ax,
                color=cores[categoria],
                edgecolor="none",
                hatch="///" if categoria in {"P75 indeterminado", "P75, P80 indeterminado"} else None,
                zorder=3,
            )
    _limites_region(ax, limites)
    ax.set_axis_off()
    ax.set_aspect("equal")
    _escala(ax, limites)
    _norte(ax, limites)
    _titulo(fig, "M09")
    handles = [
        Patch(
            facecolor=cores[c],
            edgecolor="0.5",
            hatch="///" if c in {"P75 indeterminado", "P75, P80 indeterminado"} else None,
            label=c,
        )
        for c in ordem
    ]
    side.legend(handles=handles, loc="upper left", bbox_to_anchor=(-0.04, 1.0), frameon=False, fontsize=7.5)
    contagens = mapa["_categoria"].value_counts().to_dict()
    persistentes = int(
        contagens.get("Persistente, composição alterada", 0)
        + contagens.get("Persistente, mesmo vetor", 0)
    )
    side.text(0, 0.38, "Síntese corrente", fontweight="bold", fontsize=9.5)
    side.text(
        0,
        0.33,
        (
            f"Persistentes P75–P80: {persistentes:,}\n"
            f"Mesmo vetor: {int(contagens.get('Persistente, mesmo vetor', 0)):,}\n"
            f"Composição alterada: {int(contagens.get('Persistente, composição alterada', 0)):,}\n"
            f"Não persistentes com P80 observado: {int(contagens.get('P75, não persistente no P80', 0)):,}\n"
            f"P75 com P80 indeterminado: {int(contagens.get('P75, P80 indeterminado', 0)):,}"
        ).replace(",", "."),
        va="top",
        fontsize=7.8,
        linespacing=1.35,
    )
    side.text(
        0,
        0.08,
        (
            f"Referência histórica de persistência: {referencia_persistentes:,} setores.\n"
            "A diferença de edição é registrada, não calibrada."
        ).replace(",", "."),
        fontsize=7.4,
        va="bottom",
    )
    nota = (
        f"Comparação do critério principal P75 com P80. Edição corrente: {persistentes:,} setores persistem; "
        f"referência histórica: {referencia_persistentes:,}. Categorias hachuradas indicam indeterminação por cobertura."
    ).replace(",", ".")
    _rodape(fig, "M09", nota)
    qa = {
        "universo_setorial": int(len(mapa)),
        "categorias": {str(k): int(v) for k, v in contagens.items()},
        "persistentes_correntes": persistentes,
        "referencia_historica": int(referencia_persistentes),
        "delta": persistentes - int(referencia_persistentes),
        "mesmo_vetor_corrente": int(contagens.get("Persistente, mesmo vetor", 0)),
    }
    return _salvar(fig, destino, "M09"), qa


def plot_m12(
    setores: gpd.GeoDataFrame,
    limites: gpd.GeoDataFrame,
    destino: Path,
) -> tuple[list[Path], dict[str, object]]:
    mapa = setores.copy()
    nomes = {
        "drenagem": "Drenagem — sem bueiro/boca de lobo",
        "calcadas": "Calçadas — ausência",
        "pavimentacao": "Pavimentação — ausência",
        "arborizacao": "Arborização — ausência",
        "iluminacao": "Iluminação pública — ausência",
    }
    fig = plt.figure(figsize=(12.2, 8.7))
    _titulo(fig, "M12")
    posicoes = [
        (0.04, 0.50, 0.28, 0.36),
        (0.36, 0.50, 0.28, 0.36),
        (0.68, 0.50, 0.28, 0.36),
        (0.20, 0.12, 0.28, 0.31),
        (0.52, 0.12, 0.28, 0.31),
    ]
    qa_componentes: dict[str, object] = {}
    for (chave, coluna), posicao in zip(M12_COMPONENTES.items(), posicoes, strict=True):
        ax = fig.add_axes(posicao)
        _base_region(ax, limites)
        classes, bins, rotulos = classificar_zero_mais_quantis(
            mapa[coluna], n_classes_positivas=4, casas=1
        )
        mapa[f"_classe_{chave}"] = classes
        cmap = plt.get_cmap("viridis", len(rotulos))
        cores = {rotulo: cmap(i) for i, rotulo in enumerate(rotulos)}
        _plot_classes(ax, mapa, f"_classe_{chave}", rotulos, cores)
        ausentes = mapa.loc[pd.to_numeric(mapa[coluna], errors="coerce").isna()]
        if not ausentes.empty:
            ausentes.plot(ax=ax, color="0.82", edgecolor="none", zorder=2)
        _limites_region(ax, limites)
        ax.set_axis_off()
        ax.set_aspect("equal")
        ax.set_title(nomes[chave], fontsize=8.8, fontweight="bold", pad=2)
        handles = [Patch(facecolor=cores[r], edgecolor="0.4", label=r) for r in rotulos]
        handles.append(Patch(facecolor="0.82", edgecolor="0.5", label="Sem informação"))
        ax.legend(
            handles=handles,
            title="% de moradores",
            loc="lower left",
            fontsize=5.7,
            title_fontsize=6.4,
            frameon=True,
            framealpha=0.88,
            borderpad=0.35,
            labelspacing=0.25,
            handlelength=1.2,
        )
        valores = pd.to_numeric(mapa[coluna], errors="coerce")
        qa_componentes[chave] = {
            "coluna": coluna,
            "n_validos": int(valores.notna().sum()),
            "n_ausentes": int(valores.isna().sum()),
            "limites_classes": bins,
            "rotulos_classes": rotulos,
            "min": float(valores.min()),
            "mediana": float(valores.median()),
            "max": float(valores.max()),
        }
    ax0 = fig.axes[0]
    _escala(ax0, limites, x_frac=0.04, y_frac=0.92, label_above=False)
    _norte(ax0, limites)
    nota = (
        "Cada painel separa ausência observada (0%) e usa quartis próprios entre valores positivos. "
        "Percentual de moradores em vias sem o atributo indicado; setores sem informação publicada aparecem em cinza."
    )
    _rodape(fig, "M12", nota)
    return _salvar(fig, destino, "M12"), {
        "universo_setorial": int(len(mapa)),
        "componentes": qa_componentes,
        "metodo_classes": "zero_separado_mais_quartis_dos_valores_positivos_por_componente",
    }
