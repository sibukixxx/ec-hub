"""設定ファイルの読み込み・管理."""

from __future__ import annotations

import copy
import logging
import os
from pathlib import Path

import yaml

from ec_hub.config_schema import FeeRules, Settings

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"

# Environment variable prefix for overrides
_ENV_PREFIX = "EC_HUB_"


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base dict (override wins)."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _apply_env_overrides(data: dict) -> dict:
    """Apply environment variable overrides to settings dict.

    Format: EC_HUB_<SECTION>__<KEY> (double underscore separates nesting).
    Example: EC_HUB_EBAY__APP_ID overrides data["ebay"]["app_id"]
    """
    for key, value in os.environ.items():
        if not key.startswith(_ENV_PREFIX):
            continue
        parts = key[len(_ENV_PREFIX) :].lower().split("__")
        if len(parts) != 2:
            continue
        section, field = parts
        if section not in data:
            data[section] = {}
        data[section][field] = value
    return data


def load_settings(path: Path | None = None) -> Settings:
    """settings.yaml を読み込み、型付き Settings モデルを返す.

    Priority: settings.yaml < settings.local.yaml < environment variables
    """
    p = path or _CONFIG_DIR / "settings.yaml"
    with open(p, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    # Overlay settings.local.yaml if it exists (same directory as base)
    local_path = p.parent / "settings.local.yaml"
    if local_path.exists():
        with open(local_path, encoding="utf-8") as f:
            local_raw = yaml.safe_load(f) or {}
        raw = _deep_merge(raw, local_raw)
        logger.info("Loaded local settings overlay: %s", local_path)

    raw = _apply_env_overrides(raw)
    return Settings.model_validate(raw)


def load_fee_rules(path: Path | None = None) -> FeeRules:
    """fee_rules.yaml を読み込み、型付き FeeRules モデルを返す."""
    p = path or _CONFIG_DIR / "fee_rules.yaml"
    with open(p, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return FeeRules.model_validate(raw)
