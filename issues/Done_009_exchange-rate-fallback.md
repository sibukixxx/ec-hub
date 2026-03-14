# Issue #009: 為替レート取得のフォールバック改善

## 概要
為替レート取得失敗時に固定値 150.0 JPY/USD にフォールバックするため、
レートが大きく変動した場合に利益計算が不正確になる。

## 現状
- exchangerate-api.com から取得
- 失敗時 → ハードコード 150.0
- キャッシュなし（毎回 API コール）

## やるべきこと
- [ ] 為替レートのキャッシュ（最終取得成功値を DB に保存）
- [ ] 複数の為替レート API をフォールバックチェーン化
- [ ] フォールバック使用時の警告表示（Dashboard / 通知）
- [ ] レート更新間隔の設定（デフォルト: 1時間）

## 優先度
**低** — 現状動作するが、精度に影響

## 関連ファイル
- `src/ec_hub/modules/profit_tracker.py`
- `src/ec_hub/api.py`

## 完了確認
- `src/ec_hub/modules/profit_tracker.py` で `exchange_rate_cache` を使った最終成功レートの DB 永続化と TTL キャッシュを実装済み
- `exchange_rate.base_url` と `exchange_rate.fallback_urls` を順に試すフォールバックチェーン、および `exchange_rate.cache_ttl_minutes` による更新間隔設定が入った
- API 失敗時は保存済みレートまたは静的フォールバックへ段階的に退避し、`integration_status` 更新と LINE 通知を行う
- フロントエンドの Dashboard では `exchange_rate` の health 状態を参照してフォールバック利用中の警告を表示する
