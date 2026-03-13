"""CSV形式でのデータエクスポート."""

from __future__ import annotations

import csv
from pathlib import Path

from ec_hub.models import Product


def export_csv(products: list[Product], output_path: Path) -> Path:
    """商品リストをCSVファイルにエクスポートする."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "item_id",
        "title",
        "price",
        "currency",
        "condition",
        "url",
        "image_url",
        "seller_name",
        "shipping_cost",
        "free_shipping",
        "location",
        "category",
        "bids",
        "buy_it_now",
        "scraped_at",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in products:
            writer.writerow({
                "item_id": p.item_id,
                "title": p.title,
                "price": p.price,
                "currency": p.currency,
                "condition": p.condition.value,
                "url": p.url,
                "image_url": p.image_url,
                "seller_name": p.seller.name if p.seller else "",
                "shipping_cost": p.shipping.cost if p.shipping else "",
                "free_shipping": p.shipping.free_shipping if p.shipping else False,
                "location": p.location or "",
                "category": p.category or "",
                "bids": p.bids or "",
                "buy_it_now": p.buy_it_now,
                "scraped_at": p.scraped_at.isoformat(),
            })

    return output_path
