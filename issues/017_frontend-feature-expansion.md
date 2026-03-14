# Issue #017: フロントエンド機能の拡充

## 概要
フロントエンドは基本的な表示・フィルタリングは動作するが、
操作系・管理系の機能が不足している。

## 現状
- Dashboard: 閲覧のみ
- Candidates: 承認/却下ボタンあり
- Orders: 閲覧のみ（ステータス更新不可）
- ProfitCalc: 計算機能のみ

## やるべきこと

### リサーチ管理
- [ ] リサーチ手動実行ボタン
- [ ] リサーチ実行ログ・進捗表示

### 出品管理
- [ ] 承認済み候補 → eBay 出品ボタン
- [ ] 出品プレビュー画面
- [ ] 出品制限表示

### 注文管理
- [ ] 注文ステータス更新 UI（仕入済み / 発送済み / 完了）
- [ ] 追跡番号入力フォーム
- [ ] 実際の仕入れコスト入力 → 利益確定

### メッセージセンター
- [ ] メッセージ受信箱
- [ ] 自動分類結果の表示
- [ ] 手動返信 UI
- [ ] エスカレーション表示

### データ管理
- [ ] CSV / JSON エクスポートボタン
- [ ] 一括操作（複数候補の承認等）

## 優先度
**中** — API エンドポイント拡充（#015）の後

## 関連ファイル
- `frontend/src/pages/*.jsx`
- `frontend/src/components/*.jsx`
- `frontend/src/api.js`

## 残課題
- `frontend/src/pages/Operations.tsx` / `Orders.tsx` / `Messages.tsx` により、リサーチ実行と進捗確認、出品実行と制限表示、注文更新、メッセージ一覧 / 手動返信、エクスポート導線までは実装済み
- ~~出品は Operations 画面からの一括実行のみで、承認済み候補ごとの出品プレビューや選択的 publish UI はまだない~~ → 出品プレビュー (GET /api/listing/preview/{id}) + 選択的出品 (POST /api/listing/run with candidate_ids) + Candidates ページに Preview ボタン・プレビューパネル・Bulk Publish 実装済み
- ~~Candidates 画面の一括承認 / 一括却下 / 一括出品などのバルク操作は未実装~~ → Bulk Approve / Bulk Reject 実装済み (POST /api/candidates/bulk-status + Candidates ページ checkbox UI)
- ~~メッセージ画面にはカテゴリ表示と手動返信がある一方、`other` 判定やエスカレーション案件を明示的に絞り込む UI はまだない~~ → カテゴリ別タブフィルタ実装済み (GET /api/messages?category=xxx + Messages ページ StatusTabs)。`other` カテゴリは "Escalation" ラベルで赤ハイライト表示
