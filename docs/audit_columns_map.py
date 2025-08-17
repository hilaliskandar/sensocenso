from __future__ import annotations
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

    from censo_app.transform import _get_external_colmap

    csv_map = root / "docs" / "columns_map.csv"
    if not csv_map.exists():
        raise SystemExit("docs/columns_map.csv não encontrado. Execute generate_column_map.py antes.")

    df = pd.read_csv(csv_map)
    total = len(df)
    mapped = df["app_equivalent"].notna().sum()
    unchanged = (df["app_equivalent"].fillna(df["parquet_column"]) == df["parquet_column"]).sum()
    changed = mapped - (mapped - (df["app_equivalent"].fillna("") == "").sum())

    # Colunas sem equivalente
    no_equiv = df[df["app_equivalent"].isna()][["parquet_column", "parquet_type"]]
    out_no_equiv = root / "docs" / "columns_map_unmapped.csv"
    no_equiv.to_csv(out_no_equiv, index=False, encoding="utf-8-sig")

    # Agrupar por tipos para visão geral
    type_counts = df["parquet_type"].value_counts().rename_axis("parquet_type").reset_index(name="count")
    out_types = root / "docs" / "columns_types_summary.csv"
    type_counts.to_csv(out_types, index=False, encoding="utf-8-sig")

    print(f"Total de colunas no Parquet: {total}")
    print(f"Com equivalente no app (não-nulo): {mapped}")
    print(f"Sem equivalente (app_equivalent vazio): {len(no_equiv)} -> salvo em {out_no_equiv}")
    print(f"Resumo de tipos salvo em {out_types}")


if __name__ == "__main__":
    main()
