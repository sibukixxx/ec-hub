"""エクスポーターのテスト."""

import csv
import json
from pathlib import Path

from ec_hub.exporters import export_csv, export_json
from ec_hub.models import Product, SearchResult


def _sample_products() -> list[Product]:
    return [
        Product(
            item_id="111",
            title="Product A",
            price=19.99,
            url="https://www.ebay.com/itm/111",
        ),
        Product(
            item_id="222",
            title="Product B",
            price=39.99,
            url="https://www.ebay.com/itm/222",
        ),
    ]


def test_export_csv(tmp_path: Path):
    products = _sample_products()
    output = tmp_path / "test.csv"
    result_path = export_csv(products, output)

    assert result_path.exists()
    with open(result_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 2
    assert rows[0]["item_id"] == "111"
    assert rows[0]["title"] == "Product A"
    assert rows[1]["price"] == "39.99"


def test_export_json_products(tmp_path: Path):
    products = _sample_products()
    output = tmp_path / "test.json"
    result_path = export_json(products, output)

    assert result_path.exists()
    with open(result_path, encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["item_id"] == "111"


def test_export_json_search_result(tmp_path: Path):
    products = _sample_products()
    result = SearchResult(query="test", total_results=2, products=products)
    output = tmp_path / "result.json"
    result_path = export_json(result, output)

    assert result_path.exists()
    with open(result_path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["query"] == "test"
    assert len(data["products"]) == 2
