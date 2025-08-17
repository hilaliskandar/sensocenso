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
    except Exception:
        pass
    out = re.sub(r"_(\d+)\s*$", "", out)
    out = re.sub(r"^\s*Com\s+", "", out, flags=re.IGNORECASE)
    out = re.sub(r"\s+no\s+domic[ií]lio\s*$", "", out, flags=re.IGNORECASE)
    out = re.sub(r"^Tipo\s+de\s+esp[eé]cie\s+é\s+", "", out, flags=re.IGNORECASE)
    out = re.sub(r"\b(\d{1,2})\s+ou\s+mais\b", r"\1+", out, flags=re.IGNORECASE)
    pattern_banheiro = cfg.get("banheiro_regex") or r"^\s*(\d{1,2}\+?)\s+banheiros?\s+de\s+uso\s+exclusivo\s+com\s+chuveiro\s+e\s+vaso\s+sanit[áa]rio\s+(?:existentes\s+no\s+domic[ií]lio)?\s*$"
    m = re.compile(pattern_banheiro, flags=re.IGNORECASE).match(out)
    if m:
        return m.group(1)
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
    if df is None or df.empty:
        return df
    roots = extract_root_from_title(title)
    out = df.copy()
    src_col = "categoria" if "categoria" in out.columns else out.columns[0]
    out["categoria_simplificada"] = (
        out[src_col].astype(str)
        .apply(strip_known_boilerplate)
        .apply(lambda s: simplify_label_by_roots(s, roots))
    )
    out["categoria_wrapped"] = out["categoria_simplificada"].apply(lambda s: wrap_label(s, width=width))
    return out
