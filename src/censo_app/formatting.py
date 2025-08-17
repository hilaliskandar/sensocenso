from __future__ import annotations
import pandas as pd


def fmt_br(n, decimals: int = 0) -> str:
    """Format number in PT-BR style (thousand sep '.', decimal ',').
    Safe for None/NaN; returns empty string in those cases.
    """
    try:
        if n is None or (isinstance(n, float) and pd.isna(n)):
            return ""
        s = f"{float(n):,.{decimals}f}"
        return s.replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        try:
            s = f"{int(n):,}".replace(",", ".")
            if decimals > 0:
                s = s + "," + ("0" * decimals)
            return s
        except Exception:
            return str(n)

# Alias em PT-BR
def formatar_br(n, casas_decimais: int = 0) -> str:
    return fmt_br(n, casas_decimais)
