# ec-hub

eBay商品データの収集・分析ツール。eBayの検索結果や商品詳細ページをスクレイピングし、CSV/JSON形式でエクスポートできます。

## セットアップ

```bash
uv sync
```

## 使い方

### 商品検索

```bash
# 基本的な検索
ec-hub search "mechanical keyboard"

# 価格フィルタ付き検索
ec-hub search "thinkpad x1" --min-price 200 --max-price 800

# 新品のみ、価格順でソート
ec-hub search "airpods pro" --condition new --sort price_asc

# 複数ページ取得してCSV出力
ec-hub search "vintage watch" --pages 3 --output results.csv

# JSON出力
ec-hub search "gaming mouse" --output results.json

# 日本のeBayで検索
ec-hub search "フィギュア" --site co.jp
```

### 商品詳細取得

```bash
# 商品IDから詳細を取得
ec-hub item 123456789

# JSON出力
ec-hub item 123456789 --output item.json
```

### Pythonから使う

```python
import asyncio
from ec_hub.scrapers import EbayScraper

async def main():
    async with EbayScraper() as scraper:
        result = await scraper.search("mechanical keyboard", page=1)
        for product in result.products:
            print(f"{product.title}: ${product.price}")

asyncio.run(main())
```

## プロジェクト構成

```
src/ec_hub/
├── __init__.py          # パッケージ初期化
├── cli.py               # CLIインターフェース
├── models.py            # データモデル (Product, SearchResult)
├── scrapers/
│   ├── __init__.py
│   └── ebay.py          # eBayスクレイパー
└── exporters/
    ├── __init__.py
    ├── csv_exporter.py   # CSV出力
    └── json_exporter.py  # JSON出力
```

## テスト

```bash
uv run pytest
```

## ライセンス

MIT
