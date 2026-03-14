# Issue #018: テストカバレッジの向上

## 概要
コアモジュールのユニットテストは良好だが、API / スクレイパー / フロントエンドの
テストが不足。インテグレーションテストも未整備。

## 現状テスト済み
- ProfitTracker: 利益計算（標準 / 重量品 / 低マージン）
- Database: CRUD 操作全般
- Messenger: Claude 分類 / キーワードフォールバック
- Researcher: 検索クエリ簡略化 / 仕入先価格検索 / 候補評価

## テスト不足
- [ ] REST API エンドポイント（リクエスト / レスポンス / エラー）
- [ ] eBay スクレイパー（HTML パース / セレクタ変更対応）
- [ ] Amazon PA-API クライアント（モック）
- [ ] 楽天 API クライアント（モック）
- [ ] Translator サービス
- [ ] Lister モジュール（出品フロー）
- [ ] OrderManager モジュール
- [ ] eBay API クライアント（モック）
- [ ] Notifier（LINE API モック）
- [ ] フロントエンド コンポーネントテスト（Preact Testing Library）
- [ ] E2E インテグレーションテスト

## 優先度
**中**

## 関連ファイル
- `tests/`

## 残課題
- バックエンド側は REST API、scraper 耐障害化、Amazon/Rakuten/Yahoo クライアント、Translator、Lister、OrderManager、eBay API、Notifier、Scheduler までテストが増えた一方、フロントエンド用のテストランナーとコンポーネントテスト基盤は未導入
- 画面操作から API まで通した E2E シナリオは未整備で、管理画面の回帰確認を自動化できていない
