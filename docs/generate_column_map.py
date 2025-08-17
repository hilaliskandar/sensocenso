from __future__ import annotations
import json
import sys
from pathlib import Path

import pandas as pd


def _add_paths(root: Path) -> None:
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    _add_paths(root)

    # Lazy imports after sys.path is prepared
    try:
        import duckdb  # type: ignore
    except Exception as e:
        raise SystemExit("duckdb não encontrado. Instale com: pip install duckdb") from e

    from config.config_loader import get_settings
    from censo_app import transform as T

    settings = get_settings() or {}
    parquet_path = (
        settings.get("paths", {}).get("parquet_default")
        or str(root / "data" / "base_integrada_final.parquet")
    )

    p = Path(parquet_path)
    if not p.exists():
        raise SystemExit(f"Arquivo Parquet não encontrado: {parquet_path}")

    # 1) Coletar nomes e tipos do Parquet usando DuckDB
    con = duckdb.connect()
    desc = con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{p.as_posix()}')"
    ).fetchdf()
    con.close()

    # desc: columns: column_name, column_type, null, key, default, extra
    cols_df = desc.rename(columns={"column_name": "parquet_column", "column_type": "parquet_type"})[
        ["parquet_column", "parquet_type"]
    ].copy()

    # 2) Determinar equivalente no app via função de alias/normalização
    dummy = pd.DataFrame(columns=cols_df["parquet_column"].tolist())
    renamed = T._rename_by_alias(dummy)
    canon_map = {orig: new for orig, new in zip(dummy.columns, renamed.columns)}

    cols_df["app_equivalent"] = cols_df["parquet_column"].map(canon_map).where(
        cols_df["parquet_column"].map(canon_map).ne(cols_df["parquet_column"]), None
    )

    # 3) Alias humano e mapeamentos de código (quando houver)
    def human_alias(col: str | None) -> str | None:
        if not col:
            return None
        # Variáveis V0001..V0007
        if col.upper().startswith("V000") and len(col) == 5:
            return T.get_variable_label(col)
        # Descritivos
        if col == "SITUACAO":
            return "Situação do Setor Censitário (macro: Urbana/Rural)"
        if col == "CD_SITUACAO":
            return "Código da Situação detalhada do Setor Censitário"
        if col == "SITUACAO_DET_TXT":
            return "Situação detalhada do Setor Censitário"
        if col == "CD_TIPO":
            return "Código do Tipo do Setor Censitário"
        if col == "TP_SETOR_TXT":
            return "Tipo do Setor Censitário"
        if col in ("CD_SETOR", "CD_MUN", "NM_MUN", "CD_UF", "NM_UF"):
            return col
        if col in ("RM_NOME", "AU_NOME", "NM_RGINT", "NM_RGI"):
            return col
        return None

    def code_map(col: str | None) -> str | None:
        if not col:
            return None
        if col == "CD_SITUACAO":
            return json.dumps(T.SITUACAO_DET_MAP, ensure_ascii=False)
        if col == "CD_TIPO":
            return json.dumps(T.TIPO_MAP, ensure_ascii=False)
        # Para variáveis V000x, o "código" é o próprio nome da variável
        if col.upper().startswith("V000") and len(col) == 5:
            label = T.get_variable_label(col)
            return json.dumps({col.upper(): label}, ensure_ascii=False)
        return None

    cols_df["human_alias"] = cols_df["app_equivalent"].map(human_alias)
    cols_df["code_map"] = cols_df["app_equivalent"].map(code_map)

    # 4) Tipo sugerido no app (conhecido para alguns campos)
    def app_type(col: str | None) -> str | None:
        if not col:
            return None
        if col in ("V0005", "V0006"):
            return "float64"
        if col.upper().startswith("V000") and len(col) == 5:
            return "numeric"
        if col in ("CD_SETOR", "CD_MUN", "CD_UF", "CD_SITUACAO", "CD_TIPO"):
            return "categorical/int"
        return None

    cols_df["app_type"] = cols_df["app_equivalent"].map(app_type)

    # 5) Ordenar e salvar
    out_cols = [
        "parquet_column",
        "parquet_type",
        "app_equivalent",
        "human_alias",
        "app_type",
        "code_map",
    ]
    cols_df = cols_df[out_cols]

    out_path = root / "docs" / "columns_map.csv"
    cols_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Mapa de colunas salvo em: {out_path}")
    print(f"Total de colunas: {len(cols_df)}")


if __name__ == "__main__":
    main()
