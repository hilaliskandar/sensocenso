from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

_BASE_DIR = Path(__file__).resolve().parent


def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            return {}
        return data
    except Exception:
        return {}


def get_settings() -> Dict[str, Any]:
    """Load app-wide settings from config/settings.yaml with fallback to empty dict."""
    return _read_yaml(_BASE_DIR / "settings.yaml")


def get_page_config(name: str) -> Dict[str, Any]:
    """Load page-specific config from config/{name}.yaml with fallback to empty dict."""
    # support both with and without .yaml suffix
    filename = name if name.endswith(".yaml") else f"{name}.yaml"
    return _read_yaml(_BASE_DIR / filename)


def cfg(path: str, default: Any = None, root: Optional[Dict[str, Any]] = None) -> Any:
    """Access nested config values using dot-separated path. E.g., cfg('paths.parquet_default')."""
    if root is None:
        root = get_settings()
    cur: Any = root
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return default
    return cur
