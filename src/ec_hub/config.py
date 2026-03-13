"""設定ファイルの読み込み・管理."""

from __future__ import annotations

from pathlib import Path

import yaml

_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"


def load_settings(path: Path | None = None) -> dict:
    """settings.yaml を読み込む."""
    p = path or _CONFIG_DIR / "settings.yaml"
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_fee_rules(path: Path | None = None) -> dict:
    """fee_rules.yaml を読み込む."""
    p = path or _CONFIG_DIR / "fee_rules.yaml"
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)
