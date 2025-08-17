from __future__ import annotations
import re
from functools import lru_cache
from typing import Any, Dict, List

import pandas as pd


@lru_cache(maxsize=1)
def _load_labels_cfg() -> Dict[str, Any]:
    """Carrega configurações de rótulos de config/rotulos.yaml, se existir."""
    try:
        from config.config_loader import get_page_config
        data = get_page_config("rotulos") or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def wrap_label(text: str, width: int | None = None, br: str = "<br>") -> str:
    cfg = _load_labels_cfg()
    if width is None:
        width = int(cfg.get("wrap_width_default", 16))
    if not isinstance(text, str):
        text = str(text) if text is not None else ""
    words = text.split()
    if not words:
        return ""
    lines: List[str] = []
    cur = words[0]
    for w in words[1:]:
        if len(cur) + 1 + len(w) <= width:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return br.join(lines)


def extract_root_from_title(title: str) -> list[str]:
    """Deriva candidatos de raiz a partir do título."""
    if not isinstance(title, str) or not title:
        return []
    t = title.strip()
    parts = re.split(r"\s*[—–\-:]\s*", t)
    cands = {t}
    for p in parts:
        p = p.strip()
        if p:
            cands.add(p)
    cleaned = set()
    for c in cands:
        cc = re.sub(r"^(Quantidade|Número|Percentual|Proporção|Tipo)\s+de\s+", "", c, flags=re.IGNORECASE).strip()
        cleaned.add(cc)
    return sorted({x for x in cleaned if len(x) >= 8}, key=len, reverse=True)


def dominant_label_prefix(labels: pd.Series) -> str:
    try:
        first_parts = labels.dropna().astype(str).str.split(",", n=1).str[0].str.strip()
        if first_parts.empty:
            return ""
        vc = first_parts.value_counts()
        top = vc.index[0] if not vc.empty else ""
        freq = int(vc.iloc[0]) if not vc.empty else 0
        if freq >= max(2, int(0.5 * len(first_parts))):
            return str(top)
        return ""
    except Exception:
        return ""


def strip_known_boilerplate(s: str) -> str:
    """Remove termos recorrentes não informativos nas categorias (configurável)."""
    if not s:
        return s
    out = s
    cfg = _load_labels_cfg()
    try:
        out = re.sub(r"\s+", " ", out).strip()
        patt_inexist = cfg.get("esgoto_inexistente_pattern") or r"^(?:Domicílios\s+Particulares\s+Permanentes\s+Ocupados,\s*)?Destina[cç][aã]o\s+do\s+esgoto\s+inexistente,\s*pois\s+n[aã]o\s+tinham\s+banheiro\s+nem\s+sanit[áa]rio\.?$"
        if re.compile(patt_inexist, flags=re.IGNORECASE).match(out):
            return "sem banheiro nem sanitário"
        patt_prefix = cfg.get("esgoto_prefix_pattern") or r"^(?:Domicílios\s+Particulares\s+Permanentes\s+Ocupados,\s*)?Destina[cç][aã]o\s+do\s+esgoto\s+do\s+banheiro\s+ou\s+sanit[áa]rio\s+ou\s+buraco\s+para\s+deje[cç][oõ]es\s*(?:é\s*)"
        out = re.sub(patt_prefix, "", out, flags=re.IGNORECASE)
        # Lixo: remover prefixos repetitivos como "Destinação do lixo do domicílio é"
        patt_lixo = cfg.get("lixo_prefix_pattern") or r"^(?:Domicílios\s+Particulares\s+Permanentes\s+Ocupados,\s*)?Destina[cç][aã]o\s+do\s+lixo(?:\s+do\s+domic[ií]lio)?\s*(?:é\s*)"
        out = re.sub(patt_lixo, "", out, flags=re.IGNORECASE)
    except Exception:
        pass
    out = re.sub(r"_(\d+)\s*$", "", out)
    out = re.sub(r"^\s*Com\s+", "", out, flags=re.IGNORECASE)
    out = re.sub(r"\s+no\s+domic[ií]lio\s*$", "", out, flags=re.IGNORECASE)
    out = re.sub(r"^Tipo\s+de\s+esp[eé]cie\s+é\s+", "", out, flags=re.IGNORECASE)
    out = re.sub(r"\b(\d{1,2})\s+ou\s+mais\b", r"\1+", out, flags=re.IGNORECASE)
    # Default tolerant regex: handle accents and mojibake (e.g., sanitÃ¡rio/domÃ­cilio)
    pattern_banheiro = (
        cfg.get("banheiro_regex")
        or r"^\s*((?:\d{1,2}|\d{1,2}\+))\s+banheiros?\s+de\s+uso\s+exclusivo\s+com\s+chuveiro\s+e\s+vaso\s+sanit\w+\s+(?:existentes\s+no\s+domic\w+)?\s*$"
    )
    # Try configured pattern first
    m = re.compile(pattern_banheiro, flags=re.IGNORECASE).match(out)
    if m:
        return m.group(1)
    # Fallback: tolerant default pattern (handles mojibake and variants)
    _tolerant = r"^\s*((?:\d{1,2}|\d{1,2}\+))\s+banheiros?\s+de\s+uso\s+exclusivo\s+com\s+chuveiro\s+e\s+vaso\s+sanit\w+\s+(?:existentes\s+no\s+domic\w+)?\s*$"
    m2 = re.compile(_tolerant, flags=re.IGNORECASE).match(out)
    if m2:
        return m2.group(1)
    # Last resort: if line starts with "<num> banheiros" just return the number
    m3 = re.compile(r"^\s*(\d{1,2}\+?)\s+banheiros?\b", flags=re.IGNORECASE).match(out)
    if m3:
        return m3.group(1)
    out = re.sub(r"\s{2,}", " ", out).strip()
    return out


def simplify_label_by_roots(label: str, roots: list[str]) -> str:
    if not isinstance(label, str):
        label = str(label) if label is not None else ""
    s = label.strip()
    if not s:
        return s
    for r in roots:
        if not r:
            continue
        r_esc = re.escape(r)
        s = re.sub(rf"^(?:{r_esc})\s*:\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(rf"^(?:{r_esc})\s*,\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(rf"^(?:{r_esc})\s*", "", s, flags=re.IGNORECASE)
    return s.strip()


def apply_simplify_and_wrap(df: pd.DataFrame, title: str, width: int | None = None) -> pd.DataFrame:
    """Simplifica rótulos com base no título e padrões configurados, depois aplica quebra de linha.

    Regras adicionais:
    - Considera também o prefixo dominante das categorias (antes da primeira vírgula) como possível raiz a remover.
    - Inclui raízes extras recorrentes em domicílios (DPPO/DPIO/DCCM) para reduzir duplicações.
    """
    if df is None or df.empty:
        return df
    out = df.copy()
    src_col = "categoria" if "categoria" in out.columns else out.columns[0]

    # Candidatos a raiz: do título, do prefixo dominante e extras comuns
    roots = extract_root_from_title(title)
    try:
        dom_prefix = dominant_label_prefix(out[src_col])
        if dom_prefix:
            roots = list(roots) + [dom_prefix]
    except Exception:
        pass
    extra_roots = [
        "Domicílios Particulares Permanentes Ocupados",
        "Domicílios Particulares Improvisados Ocupados",
        "Unidades de Habitação em Domicílios Coletivos Com Morador",
    ]
    for er in extra_roots:
        if er not in roots:
            roots.append(er)

    out["categoria_simplificada"] = (
        out[src_col]
        .astype(str)
        .apply(strip_known_boilerplate)
        .apply(lambda s: simplify_label_by_roots(s, roots))
    )
    out["categoria_wrapped"] = out["categoria_simplificada"].apply(lambda s: wrap_label(s, width=width))
    return out
