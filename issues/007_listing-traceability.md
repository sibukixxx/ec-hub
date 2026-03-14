# Issue #007: 出品在庫テーブル追加と受注トレース強化

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

## 残課題
- `OrderManager` は SKU / `listingId` / `offerId` から `listing_id` と `candidate_id` を逆引きできるようになったが、複数 line item を含む注文でも `orders` レコードには先頭の 1 件しか保持しておらず、明細単位のトレースはできない
- `messages` / `orders` / `listings` / `candidates` の関連は DB と手動返信フローで辿れる一方、`Messenger.check_new_messages()` が未実装のため、実際の eBay 受信メッセージを自動で紐付ける経路はまだない
- 状態遷移は `Lister` と `OrderManager` 内に分散しており、`listed` / `sold` / `completed` / `cancelled` / `returned` を横断した一貫した状態機械は未整備
