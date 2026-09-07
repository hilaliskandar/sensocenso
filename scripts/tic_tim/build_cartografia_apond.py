#!/usr/bin/env python3
"""Constrói a base cartográfica municipal APOND de forma parametrizada.

Entradas e regras seguem o Procedimento Operacional Multimunicípio APOND v1.
O script não contém hardcodes municipais: município, código IBGE, APONDs,
rótulos e contagens esperadas são fornecidos por JSON de configuração.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def norm_setor(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.extract(r"(\d{15})", expand=False)
        .astype("string")
    )


def locate_shp(path: Path, contains: str | None = None) -> Path:
    if path.is_file() and path.suffix.lower() == ".shp":
        return path
    candidates = sorted(path.rglob("*.shp"))
    if contains:
        filtered = [p for p in candidates if contains in p.name or contains in str(p)]
        if filtered:
            candidates = filtered
    if not candidates:
        raise FileNotFoundError(f"Nenhum shapefile encontrado em {path}")
    return candidates[0]


def read_config(path: Path) -> dict[str, Any]:
    cfg = json.loads(path.read_text(encoding="utf-8"))
    required = [
        "municipio", "slug", "cd_mun", "n_setores", "n_aponds",
        "apond_names", "apond_labels", "expected_setores_por_apond",
    ]
    missing = [k for k in required if k not in cfg]
    if missing:
        raise ValueError(f"Configuração incompleta: {missing}")
    return cfg


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--matriz", required=True, type=Path)
    ap.add_argument("--setores", required=True, type=Path, help="Shapefile ou diretório contendo a malha setorial")
    ap.add_argument("--faces", required=True, type=Path, help="Shapefile ou diretório contendo as faces municipais")
    ap.add_argument("--out-dir", required=True, type=Path)
    args = ap.parse_args()

    cfg = read_config(args.config)
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    mapping = pd.read_csv(args.matriz, dtype=str)
    if "CD_SETOR" not in mapping.columns or "APOND" not in mapping.columns:
        raise ValueError("A matriz deve conter CD_SETOR e APOND")
    mapping["CD_SETOR"] = norm_setor(mapping["CD_SETOR"])
    if mapping["CD_SETOR"].isna().any():
        raise ValueError("Há CD_SETOR inválido na matriz")
    if len(mapping) != int(cfg["n_setores"]) or mapping["CD_SETOR"].nunique() != int(cfg["n_setores"]):
        raise AssertionError(("matriz", len(mapping), mapping["CD_SETOR"].nunique(), cfg["n_setores"]))

    expected_dist = {str(k): int(v) for k, v in cfg["expected_setores_por_apond"].items()}
    got_dist = {str(k): int(v) for k, v in mapping.groupby("APOND").size().to_dict().items()}
    if got_dist != expected_dist:
        raise AssertionError(("distribuicao_apond", got_dist, expected_dist))

    setores_shp = locate_shp(args.setores)
    setores = gpd.read_file(setores_shp, where=f"CD_MUN = '{cfg['cd_mun']}'", engine="pyogrio")
    if "CD_SETOR" not in setores.columns:
        raise ValueError("Malha oficial sem CD_SETOR")
    setores["CD_SETOR"] = norm_setor(setores["CD_SETOR"])
    setores = setores[setores["CD_SETOR"].isin(set(mapping["CD_SETOR"]))].copy()

    missing = sorted(set(mapping["CD_SETOR"]) - set(setores["CD_SETOR"]))
    extra = sorted(set(setores["CD_SETOR"]) - set(mapping["CD_SETOR"]))
    if len(setores) != int(cfg["n_setores"]) or setores["CD_SETOR"].nunique() != int(cfg["n_setores"]) or missing or extra:
        raise AssertionError({"n_setores": len(setores), "n_unicos": setores["CD_SETOR"].nunique(), "missing": missing, "extra": extra})

    setores = setores.merge(mapping, on="CD_SETOR", how="left", validate="one_to_one")
    if setores["APOND"].isna().any():
        raise AssertionError("APOND ausente após merge setorial")
    if setores.crs is None:
        setores = setores.set_crs(4674)
    else:
        setores = setores.to_crs(4674)

    names = {str(k): str(v) for k, v in cfg["apond_names"].items()}
    labels = {str(k): str(v) for k, v in cfg["apond_labels"].items()}
    setores["ROTULO"] = setores["APOND"].map(labels)
    setores["NOME_APOND"] = setores["APOND"].map(names)
    if setores[["ROTULO", "NOME_APOND"]].isna().any().any():
        raise AssertionError("APOND sem rótulo/nome na configuração")

    aponds = setores[["APOND", "ROTULO", "NOME_APOND", "geometry"]].dissolve(
        by=["APOND", "ROTULO", "NOME_APOND"], as_index=False
    )
    if len(aponds) != int(cfg["n_aponds"]):
        raise AssertionError(("n_aponds", len(aponds), cfg["n_aponds"]))

    faces_shp = locate_shp(args.faces, contains=str(cfg["cd_mun"]))
    faces = gpd.read_file(faces_shp)
    if faces.crs is None:
        faces = faces.set_crs(4674)
    else:
        faces = faces.to_crs(4674)
    if "CD_SETOR" in faces.columns:
        faces["CD_SETOR_ORIG"] = faces["CD_SETOR"].astype(str)
        faces["CD_SETOR"] = norm_setor(faces["CD_SETOR"])
        faces = faces[faces["CD_SETOR"].isin(set(mapping["CD_SETOR"]))].copy()
        faces = faces.merge(mapping[["CD_SETOR", "APOND"]], on="CD_SETOR", how="left", validate="many_to_one")
        if faces.empty or faces["APOND"].isna().any():
            raise AssertionError("Faces vazias ou sem associação APOND")
    else:
        raise ValueError("Camada de faces sem CD_SETOR; associação canônica indisponível")

    prefix = f"TIC_TIM_Censo2022_{cfg['slug']}_APOND"
    gpkg = out / f"{prefix}_base_territorial_v1.gpkg"
    png = out / f"{prefix}_mapa_abertura_v1.png"
    qa_path = out / f"TIC_TIM_Censo2022_{cfg['slug']}_QA_CARTOGRAFIA_v1.json"
    if gpkg.exists():
        gpkg.unlink()

    setores.to_file(gpkg, layer="setores", driver="GPKG")
    aponds.to_file(gpkg, layer="aponds", driver="GPKG")
    faces.to_file(gpkg, layer="faces", driver="GPKG")

    # Preflight de leitura das três camadas imediatamente após a escrita.
    preflight = {}
    for layer, expected in [("setores", int(cfg["n_setores"])), ("aponds", int(cfg["n_aponds"]))]:
        chk = gpd.read_file(gpkg, layer=layer)
        preflight[layer] = {"n": int(len(chk)), "crs": str(chk.crs)}
        if len(chk) != expected:
            raise AssertionError(("preflight", layer, len(chk), expected))
    chk_faces = gpd.read_file(gpkg, layer="faces")
    preflight["faces"] = {"n": int(len(chk_faces)), "crs": str(chk_faces.crs)}
    if chk_faces.empty:
        raise AssertionError("Preflight: camada faces vazia")

    fig, ax = plt.subplots(figsize=(10, 8))
    aponds.plot(ax=ax, alpha=0.20, edgecolor="black", linewidth=1.2)
    faces.plot(ax=ax, linewidth=0.25, alpha=0.55)
    aponds.boundary.plot(ax=ax, linewidth=1.4)
    pts = aponds.representative_point()
    for (_, row), pt in zip(aponds.iterrows(), pts):
        ax.text(pt.x, pt.y, row["ROTULO"], ha="center", va="center", fontsize=12, fontweight="bold")
    ax.set_title(f"{cfg['municipio']} — Áreas de Ponderação do Censo 2022")
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(png, dpi=180, bbox_inches="tight")
    plt.close(fig)

    sit_col = next((c for c in ["SITUACAO", "CD_SIT", "CD_SITUACAO"] if c in setores.columns), None)
    situacao = {}
    if sit_col:
        situacao = {str(k): int(v) for k, v in setores[sit_col].fillna("NA").astype(str).value_counts(dropna=False).to_dict().items()}

    qa = {
        "status": "PASS",
        "procedimento": "APOND_CARTOGRAFIA_PARAMETRIZADA_V1",
        "municipio": cfg["municipio"],
        "cd_mun": str(cfg["cd_mun"]),
        "crs": "EPSG:4674",
        "n_setores": int(len(setores)),
        "n_setores_unicos": int(setores["CD_SETOR"].nunique()),
        "n_aponds": int(len(aponds)),
        "n_faces": int(len(faces)),
        "setores_por_apond": {str(k): int(v) for k, v in setores.groupby("APOND").size().to_dict().items()},
        "setores_faltantes": missing,
        "setores_extras": extra,
        "situacao_setorial": situacao,
        "preflight_gpkg": preflight,
        "fontes": {
            "setores": str(setores_shp),
            "faces": str(faces_shp),
            "matriz": str(args.matriz),
            "config": str(args.config),
        },
    }
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    qa["sha256"] = {"gpkg": sha256(gpkg), "png": sha256(png), "qa_json": sha256(qa_path)}
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(qa, ensure_ascii=False, indent=2))
    for p in [gpkg, png, qa_path]:
        print(p, p.stat().st_size, sha256(p))


if __name__ == "__main__":
    main()
