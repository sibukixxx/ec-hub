"""JSON形式でのデータエクスポート."""

from __future__ import annotations

import json
from pathlib import Path

from ec_hub.models import Product, SearchResult


def export_json(data: SearchResult | list[Product], output_path: Path) -> Path:
    """検索結果または商品リストをJSONファイルにエクスポートする."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(data, SearchResult):
        json_data = data.model_dump(mode="json")
    else:
        json_data = [p.model_dump(mode="json") for p in data]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    return output_path
