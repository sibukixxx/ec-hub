# ec-hub

eBay輸出転売 自動化システム。リサーチ・出品・受注管理・バイヤー対応を自動化し、1人でスケーラブルな運用を可能にする。

## セットアップ

### 前提ツールのインストール

#### uv (Python パッケージマネージャ)

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Homebrew (macOS)
brew install uv
```

#### pnpm (Node.js パッケージマネージャ)

```bash
# corepack 経由 (推奨)
corepack enable && corepack prepare pnpm@latest --activate

# または npm 経由
npm install -g pnpm
```

### ローカルセットアップ

```bash
# バックエンド
uv sync
cp config/settings.yaml config/settings.local.yaml  # API キーを設定

# フロントエンド
cd frontend && pnpm install
```

### Docker セットアップ

Docker を使えばツールの個別インストールは不要。

```bash
# 全サービス起動 (バックエンド + フロントエンド)
docker compose up

# バックグラウンド起動
docker compose up -d

# バックエンドのみ
docker compose up backend

# リビルド
docker compose up --build

# テスト実行
docker compose run --rm backend uv run pytest

# リンター実行
docker compose run --rm backend uv run ruff check src/ tests/
```

`config/` と `db/` はホストからマウントされるため、設定やデータはローカルに永続化される。

## 使い方

### Web ダッシュボード

```bash
# APIサーバー起動
uv run uvicorn ec_hub.api:app --reload

# フロントエンド開発サーバー
cd frontend && pnpm dev
```

ダッシュボードでは以下を操作できる:
- **Dashboard** - 候補数・注文数・累計利益・為替レートの概要
- **Candidates** - リサーチ候補の承認・却下管理
- **Orders** - 注文のステータス追跡
- **ProfitCalc** - 利益シミュレーター

### CLI

```bash
# 商品検索
ec-hub search "mechanical keyboard"
ec-hub search "thinkpad x1" --min-price 200 --max-price 800
ec-hub search "airpods pro" --condition new --sort price_asc
ec-hub search "vintage watch" --pages 3 --output results.csv

# 商品詳細取得
ec-hub item 123456789

# 利益シミュレーション (仕入れ¥3,000、eBay $80、重量500g、配送先US)
ec-hub calc --cost 3000 --price 80 --weight 500 --dest US

# 自動リサーチ実行
ec-hub research --keywords "mechanical keyboard" --pages 2

# 候補・注文管理
ec-hub candidates --status pending
ec-hub orders --status awaiting_purchase
```

### Python API

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

### REST API

| メソッド | エンドポイント | 説明 |
|---------|--------------|------|
| GET | `/api/dashboard` | ダッシュボード統計 |
| GET | `/api/candidates` | 候補一覧 (フィルタ・ページネーション) |
| GET/PATCH | `/api/candidates/{id}` | 候補の取得・ステータス更新 |
| GET | `/api/orders` | 注文一覧 |
| GET | `/api/orders/{id}` | 注文詳細 |
| POST | `/api/calc/profit` | 利益計算 |

## モジュール構成

| モジュール | 役割 | 概要 |
|-----------|------|------|
| **Researcher** | 価格差リサーチ | eBay→Amazon/楽天クロス検索、利益率30%以上の候補を自動抽出 |
| **Profit Tracker** | 利益計算 | eBay手数料・Payoneer手数料・送料・FXバッファを含む純利益算出 |
| **Lister** | eBay自動出品 | DeepL翻訳→価格設定→eBay Inventory API出品 |
| **Order Manager** | 受注管理 | 受注検知→仕入れ→発送→完了のライフサイクル管理 |
| **Messenger** | バイヤー応答 | Claude Haikuによるメッセージ分類+テンプレート自動返信 |
| **Notifier** | LINE通知 | 候補発見・新規注文・出品上限警告等の通知 |

## データソース

| ソース | 方式 | 用途 |
|--------|------|------|
| eBay | HTTPスクレイピング | 商品検索・価格調査 |
| Amazon | PA-API 5.0 | 仕入れ価格比較 |
| 楽天市場 | Ichiba API | 仕入れ価格比較 |
| eBay REST API | OAuth認証 | 出品・注文管理・フルフィルメント |
| DeepL | REST API | 商品タイトル翻訳 (JP→EN) |

## プロジェクト構成

```
src/ec_hub/
├── api.py               # FastAPI REST API
├── cli.py               # CLIインターフェース
├── config.py            # 設定管理
├── models.py            # Pydanticデータモデル
├── scrapers/
│   ├── base.py          # 抽象基底クラス
│   ├── ebay.py          # eBayスクレイパー
│   ├── amazon.py        # Amazon PA-APIクライアント
│   └── rakuten.py       # 楽天APIクライアント
├── exporters/
│   ├── csv_exporter.py  # CSV出力
│   └── json_exporter.py # JSON出力
├── modules/
│   ├── researcher.py     # リサーチエンジン
│   ├── profit_tracker.py # 利益計算
│   ├── lister.py         # 自動出品
│   ├── order_manager.py  # 受注管理
│   ├── messenger.py      # バイヤー応答
│   └── notifier.py       # LINE通知
├── services/
│   ├── ebay_api.py       # eBay API統合クライアント
│   └── translator.py     # 翻訳サービス
└── db/
    └── database.py       # SQLiteデータベース

frontend/                 # Preact SPA ダッシュボード
config/
├── settings.yaml         # システム設定
└── fee_rules.yaml        # 手数料・送料ルール
```

## テスト

```bash
uv run pytest
uv run pytest tests/test_scraper.py -v  # 個別テスト
```

## ライセンス

MIT
