from __future__ import annotations
import pandas as pd
from typing import List, Optional

from .formatting import fmt_br


def build_abnt_demographic_table(df_plot: pd.DataFrame, age_order: List[str]) -> pd.DataFrame:
    """Build ABNT-style demographic table from df_plot with columns
    ['faixa_etaria','sexo','populacao'].
    Returns a DataFrame with columns: Faixa Etária, Masculino, Feminino, Total, % Masculino, % Feminino
    and a TOTAL row appended.
    """
    pivot = (
        df_plot.pivot_table(
            index='faixa_etaria', columns='sexo', values='populacao', aggfunc='sum', fill_value=0
        )
        .reset_index()
        .rename(columns={'faixa_etaria': 'Faixa Etária'})
    )
    for col in ("Masculino", "Feminino"):
        if col not in pivot.columns:
            pivot[col] = 0
    pivot['Total'] = pivot['Masculino'] + pivot['Feminino']
    mask = pivot['Total'] > 0
    pivot['% Masculino'] = 0.0
    pivot['% Feminino'] = 0.0
    pivot.loc[mask, '% Masculino'] = (pivot.loc[mask, 'Masculino'] / pivot.loc[mask, 'Total'] * 100).round(1)
    pivot.loc[mask, '% Feminino'] = (pivot.loc[mask, 'Feminino'] / pivot.loc[mask, 'Total'] * 100).round(1)

    # Sort by canonical order with fallback by numeric lower bound
    def _ord(lbl: str) -> int:
        try:
            if lbl in age_order:
                return age_order.index(lbl)
            import re
            m = re.search(r"(\d+)\s*a\s*(\d+)", str(lbl))
            if m:
                return int(m.group(1))
            m = re.search(r"(\d+)\s*anos?\s*ou\s*mais", str(lbl), re.IGNORECASE)
            if m:
                return int(m.group(1))
            m = re.search(r"(\d+)", str(lbl))
            if m:
                return int(m.group(1))
        except Exception:
            pass
        return 99999

    pivot['ordem'] = pivot['Faixa Etária'].apply(_ord)
    pivot = pivot.sort_values(['ordem', 'Faixa Etária']).drop('ordem', axis=1)

    total_row = {
        'Faixa Etária': 'TOTAL',
        'Masculino': int(pivot['Masculino'].sum()),
        'Feminino': int(pivot['Feminino'].sum()),
        'Total': int(pivot['Total'].sum()),
        '% Masculino': 0.0,
        '% Feminino': 0.0,
    }
    if total_row['Total'] > 0:
        total_row['% Masculino'] = round(total_row['Masculino'] / total_row['Total'] * 100, 1)
        total_row['% Feminino'] = round(total_row['Feminino'] / total_row['Total'] * 100, 1)

    out = pd.concat([pivot, pd.DataFrame([total_row])], ignore_index=True)
    return out.reset_index(drop=True)


def render_abnt_html(df: pd.DataFrame) -> str:
    """Render a simplified ABNT table as HTML (no vertical borders)."""
    df_fmt = df.copy()

    def _fmt_delta(val):
        if pd.isna(val):
            return ""
        try:
            v = float(val)
        except Exception:
            return ""
        if abs(v) < 1e-9:
            return "<span style='color:#666'>—</span>"
        arrow = "▲" if v > 0 else "▼"
        color = "#0a8f2a" if v > 0 else "#c62828"
        sign = "+" if v > 0 else ""
        return f"<span style='color:{color}; font-weight:600'>{arrow} {sign}{fmt_br(abs(v), 1)} pp</span>"

    fmt = {
        "Masculino": lambda x: fmt_br(x, 0),
        "Feminino": lambda x: fmt_br(x, 0),
        "Total": lambda x: fmt_br(x, 0),
        "% Masculino": lambda x: (fmt_br(x, 1) + "%") if pd.notna(x) else "",
        "% Feminino": lambda x: (fmt_br(x, 1) + "%") if pd.notna(x) else "",
        "% do Total": lambda x: (fmt_br(x, 1) + "%") if pd.notna(x) else "",
        "Δ vs Comp.": None,
    }
    for col, f in fmt.items():
        if col in df_fmt.columns and f is not None:
            df_fmt[col] = df_fmt[col].apply(lambda x: f(x) if pd.notna(x) else "")
        if col == "Δ vs Comp." and col in df_fmt.columns:
            df_fmt[col] = df_fmt[col].apply(_fmt_delta)

    thead = "<tr>" + "".join(f"<th>{c}</th>" for c in df_fmt.columns) + "</tr>"
    rows = []
    for _, r in df_fmt.iterrows():
        tds = "".join(f"<td>{r[c]}</td>" for c in df_fmt.columns)
        rows.append(f"<tr>{tds}</tr>")
    tbody = "".join(rows)
    css = """
    <style>
    table.abnt {border-collapse: collapse; width: 100%; border-top: 2px solid #000; border-bottom: 2px solid #000; font-family: Arial, 'Times New Roman', serif; font-size: 12px;}
    table.abnt th, table.abnt td {padding: 6px 10px; text-align: right; border-left: none; border-right: none;}
    table.abnt th:first-child, table.abnt td:first-child {text-align: left;}
    table.abnt thead th {text-align: left;}
    </style>
    """
    html = f"{css}<table class='abnt'><thead>{thead}</thead><tbody>{tbody}</tbody></table>"
    return html

# Aliases em PT-BR
def montar_tabela_demografica_abnt(df_pivot: pd.DataFrame, ordem_idade: List[str]) -> pd.DataFrame:
    return build_abnt_demographic_table(df_pivot, ordem_idade)

def renderizar_abnt_html(df: pd.DataFrame) -> str:
    return render_abnt_html(df)
