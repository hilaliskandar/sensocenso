from __future__ import annotations
from typing import Any

def clean_label(val: Any) -> Any:
    """Return a cleaned label or pandas.NA-compatible None when empty/undefined.
    Keeps original value type for non-string inputs where possible.
    """
    try:
        s = str(val).strip()
    except Exception:
        return None
    low = s.lower()
    if low in {"", "nan", "none", "undefined", "null", "-", "—"}:
        return None
    return s


def sanitize_title(title: str | None) -> str:
    """Ensure titles never show as undefined/nan/empty.
    Normalizes separators and removes empty right-hand parts.
    """
    try:
        s = str(title or "").replace("–", "—").strip()
        if not s:
            return "Estado de São Paulo"
        low = s.lower()
        if low in ("nan", "none", "undefined", "null"):
            return "Estado de São Paulo"
        if "—" in s:
            left, right = s.split("—", 1)
            right = right.strip()
            if right == "" or right.lower() in ("nan", "none", "undefined", "null"):
                return "Estado de São Paulo"
        elif "-" in s:
            left, right = s.split("-", 1)
            right = right.strip()
            if right == "" or right.lower() in ("nan", "none", "undefined", "null"):
                return "Estado de São Paulo"
        return s
    except Exception:
        return "Estado de São Paulo"


def wrap_title(text: str, width: int = 42) -> str:
    """Wrap long titles with <br> breaks to improve layout stability."""
    try:
        import textwrap
        parts = textwrap.wrap(str(text), width=width)
        return "<br>".join(parts) if parts else str(text)
    except Exception:
        return str(text)

# Aliases em PT-BR
def limpar_rotulo(valor: Any) -> Any:
    return clean_label(valor)

def sanitizar_titulo(titulo: str | None) -> str:
    return sanitize_title(titulo)

def quebrar_titulo(texto: str, largura: int = 42) -> str:
    return wrap_title(texto, width=largura)
