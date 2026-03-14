# Issue #016: 設定管理 UI の追加

## 概要
API キーや各種設定が YAML ファイルの手動編集でしか変更できない。
Web UI から設定を管理できるようにする。

## 現状
- `config/settings.yaml` を手動編集
- API キーのバリデーションなし
- 接続テスト機能なし

## やるべきこと
- [ ] `GET /api/config` — 現在の設定取得（キーはマスク表示）
- [ ] `PUT /api/config` — 設定更新
- [ ] `POST /api/config/test/{service}` — API 接続テスト
- [ ] フロントエンドに設定ページ追加
  - eBay API 設定
  - Amazon PA-API 設定
  - 楽天 API 設定
  - DeepL / Claude API 設定
  - LINE Messaging API 設定
  - 手数料・送料ルール編集
- [ ] 設定変更時のバリデーション
- [ ] 機密情報の安全な保存（環境変数 or 暗号化）

## 優先度
**中** — 運用開始前に必要

## 関連ファイル
- `src/ec_hub/config.py`
- `config/settings.yaml`
- `config/fee_rules.yaml`
