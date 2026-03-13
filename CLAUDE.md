# CLAUDE.md

## プロジェクト概要

ec-hub: eBay輸出転売の自動化システム。リサーチ・出品・受注管理・バイヤー対応を自動化する。

## 技術スタック

- **Backend:** Python 3.11+, FastAPI, SQLite (aiosqlite), Pydantic v2
- **Frontend:** Preact 10, Vite 7, pnpm
- **外部API:** eBay REST API, Amazon PA-API 5.0, Rakuten Ichiba API, DeepL, Claude Haiku, LINE Messaging API
- **スクレイピング:** httpx + BeautifulSoup + lxml
- **テスト:** pytest, pytest-asyncio
- **リンター:** ruff

## ビルド・実行コマンド

```bash
# 依存関係インストール
uv sync

# テスト実行
uv run pytest

# 単一テスト実行
uv run pytest tests/test_scraper.py -v

# リンター
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# APIサーバー起動
uv run uvicorn ec_hub.api:app --reload

# フロントエンド開発
cd frontend && pnpm install && pnpm dev

# CLI
uv run ec-hub search "keyword"
uv run ec-hub calc --cost 3000 --price 80 --weight 500 --dest US
```

## プロジェクト構造

```
src/ec_hub/
├── api.py              # FastAPI REST API (/api/dashboard, /api/candidates, /api/orders, /api/calc/profit)
├── cli.py              # CLIインターフェース (search, item, calc, research, candidates, orders)
├── config.py           # YAML設定ローダー
├── models.py           # Pydanticモデル (Product, Candidate, Order, ProfitBreakdown等 25クラス)
├── scrapers/
│   ├── base.py         # 抽象基底クラス (SourceSearcher, SourceProduct)
│   ├── ebay.py         # eBayスクレイパー (検索・詳細取得・リトライ)
│   ├── amazon.py       # Amazon PA-API 5.0クライアント
│   └── rakuten.py      # 楽天市場APIクライアント
├── exporters/
│   ├── csv_exporter.py
│   └── json_exporter.py
├── modules/
│   ├── researcher.py     # 価格差リサーチ (eBay→Amazon/楽天クロス検索→利益判定)
│   ├── profit_tracker.py # 利益計算 (eBay手数料13.25%, Payoneer2%, 送料, FXバッファ3%)
│   ├── lister.py         # eBay自動出品 (翻訳→価格設定→Inventory API)
│   ├── order_manager.py  # 受注管理 (awaiting→purchased→shipped→delivered→completed)
│   ├── messenger.py      # バイヤー自動応答 (Claude Haiku分類 + テンプレート返信)
│   └── notifier.py       # LINE通知
├── services/
│   ├── ebay_api.py       # eBay REST API統合クライアント
│   └── translator.py     # DeepL翻訳サービス
└── db/
    └── database.py       # async SQLite (candidates, orders, messages, daily_reports)

frontend/               # Preact SPA
├── src/
│   ├── app.jsx         # ルーティング
│   ├── api.js          # APIクライアント
│   ├── components/Sidebar.jsx
│   └── pages/          # Dashboard, Candidates, Orders, ProfitCalc
├── vite.config.js
└── package.json

config/
├── settings.yaml       # API キー・スケジューラ設定
└── fee_rules.yaml      # 手数料・送料ルール

tests/                  # pytest テスト
issues/                 # 課題管理 (001-010)
```

## コーディング規約

- Python: ruff準拠 (line-length=120, select=E,F,I,W)
- 非同期: async/await を標準で使用
- モデル: Pydantic v2 (model_dump, model_validate)
- DB: aiosqlite による非同期SQLite操作
- テスト: asyncio_mode="auto"
- 言語: コード・コメントは英語、ドキュメント・UIは日本語

## 重要な設計判断

- 利益率30%以上を候補登録の閾値とする
- 為替レートに3%バッファを設ける
- eBay手数料13.25% + Payoneer手数料2%で計算
- 送料はゾーン別 (US/Europe/Asia)
- Claude Haiku でメッセージ分類、フォールバックとしてキーワードマッチング
- フロントエンドは FastAPI の static files として配信
