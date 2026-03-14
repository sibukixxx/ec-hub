# Issue #014: 出品在庫テーブル追加と受注トレース強化

## 概要
このシステムは「候補承認 → 出品 → 受注 → メッセージ対応」までをつなぐ運用が前提だが、
現在は `candidate.status` を切り替えるだけで、出品そのものの実体が DB に存在しない。
結果として注文・問い合わせを元候補まで追跡しにくい。

## 現状
- `listings` テーブルがなく、`sku` / `offer_id` / `listing_id` / 出品価格が保存されない
- `Lister.list_candidate()` は翻訳タイトル・説明 HTML・為替レートを永続化しない
- `OrderManager.register_order()` は `candidate_id=None` のまま登録されるケースが前提
- メッセージも注文や出品との関連が弱く、運用分析に使いにくい

## やるべきこと
- [ ] `listings` テーブルを追加する
  - `candidate_id`
  - `sku`
  - `offer_id`
  - `listing_id`
  - `title_en`
  - `description_html`
  - `listed_price_usd`
  - `listed_fx_rate`
  - `status`
- [ ] `Lister` で eBay 送信前後のデータを保存する
- [ ] `OrderManager` で eBay order line items から listing / candidate を逆引きできるようにする
- [ ] `messages` と `orders` から listing / candidate を辿れる関連を追加する
- [ ] 候補・出品・注文の状態遷移を一貫管理する

## 優先度
**高** — 出品後の運用と分析を成立させるために必要

## 関連ファイル
- `src/ec_hub/modules/lister.py`
- `src/ec_hub/modules/order_manager.py`
- `src/ec_hub/modules/messenger.py`
- `src/ec_hub/services/ebay_api.py`
- `src/ec_hub/db/database.py`
- `src/ec_hub/models.py`
