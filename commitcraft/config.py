"""Config file persistence at ~/.commitcraft/config.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


CONFIG_DIR = Path.home() / ".commitcraft"
CONFIG_PATH = CONFIG_DIR / "config.json"


DEFAULT_CONFIG: Dict[str, Any] = {
    "default_provider": None,
    "ollama_model": None,
    "anthropic_model": None,
    "smart_mode": True,
}


def load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        return dict(DEFAULT_CONFIG)
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_CONFIG)
    merged = dict(DEFAULT_CONFIG)
    if isinstance(raw, dict):
        merged.update(raw)
    return merged


def save_config(cfg: Dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, sort_keys=True)


def update_config(**updates: Any) -> Dict[str, Any]:
    cfg = load_config()
    cfg.update(updates)
    save_config(cfg)
    return cfg
