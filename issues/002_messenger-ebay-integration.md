# Issue #002: Messenger の eBay API 連携（受信・送信）

## 概要
Messenger モジュールの分類ロジック（Claude Haiku / キーワード）は実装済みだが、
eBay からのメッセージ取得と返信送信が未実装。

## 現状
- `check_new_messages()` → 空リストを返す（TODO コメントあり）
- `handle_message()` → テンプレート返信を生成するが、実際には送信しない（TODO コメントあり）

## やるべきこと
- [ ] eBay Trading API `GetMyMessages` を使った未読メッセージ取得の実装
- [ ] eBay Trading API 経由でのメッセージ返信送信の実装
- [ ] メッセージ処理のエラーハンドリング・リトライ
- [ ] 自動応答不可（分類: other）の場合のエスカレーション通知（LINE）

## 優先度
**高** — バイヤー対応の自動化に必須

## 関連ファイル
- `src/ec_hub/modules/messenger.py` (L203, L220 に TODO)
- `src/ec_hub/services/ebay_api.py`
