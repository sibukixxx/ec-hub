# ec-hub

eBay輸出転売 自動化システム。リサーチ・出品・受注管理・バイヤー対応を自動化し、1人でスケーラブルな運用を可能にする。

## セットアップ

```bash
uv sync
cp config/settings.yaml config/settings.local.yaml  # API キーを設定
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
ec-hub item 123456789
ec-hub item 123456789 --output item.json
```

### 利益シミュレーション

```bash
# 仕入れ¥3,000、eBay $80、重量500g、配送先USで利益計算
ec-hub calc --cost 3000 --price 80 --weight 500 --dest US
```

### 候補・注文管理

```bash
# リサーチ候補一覧
ec-hub candidates --status pending

# 注文一覧
ec-hub orders --status awaiting_purchase
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

## モジュール構成

| モジュール | 役割 | 実装状況 |
|-----------|------|---------|
| **Researcher** | 価格差リサーチ・候補抽出 | Phase 2 |
| **Lister** | eBayへの自動出品 | Phase 3 |
| **Order Manager** | 受注検知・仕入れ指示 | Phase 4 |
| **Messenger** | バイヤーメッセージ自動応答 | Phase 5 |
| **Profit Tracker** | 利益計算・日次レポート | Phase 1 (実装済) |
| **Notifier** | LINE通知ハブ | Phase 1 (実装済) |

## プロジェクト構成

```
src/ec_hub/
├── cli.py               # CLIインターフェース
├── config.py            # 設定ファイル管理
├── models.py            # データモデル
├── scrapers/
│   └── ebay.py          # eBayスクレイパー
├── exporters/
│   ├── csv_exporter.py  # CSV出力
│   └── json_exporter.py # JSON出力
├── modules/
│   ├── profit_tracker.py # 利益計算
│   ├── notifier.py       # LINE通知
│   ├── researcher.py     # リサーチ
│   ├── lister.py         # 出品
│   ├── order_manager.py  # 受注管理
│   └── messenger.py      # バイヤー応答
└── db/
    └── database.py       # SQLiteデータベース
config/
├── settings.yaml        # システム設定
└── fee_rules.yaml       # 手数料・送料ルール
```

## テスト

```bash
uv run pytest
```

## ライセンス

MIT
