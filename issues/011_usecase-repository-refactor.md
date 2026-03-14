# Issue #011: ユースケース層・Repository 層への再編

## 概要
このシステムは CLI / REST API / 今後の Scheduler から同じ業務フローを叩く構成だが、
現在は各入口が直接 `Database`・設定ローダー・各モジュールを組み立てている。
輸送層と業務ロジックが密結合で、機能追加のたびに変更箇所が散る。

## 現状
- `api.py` と `cli.py` がそれぞれ `load_settings()` / `load_fee_rules()` / `Database(...)` を直接呼ぶ
- `get_candidate()` / `get_order()` / `Lister.list_candidate()` / `OrderManager.complete_order()` が一覧取得後に `next(...)` で対象を探している
- モジュール間の共通オーケストレーションがなく、ログ・エラー処理・トランザクション境界を統一できていない
- 今後 Scheduler を入れると、同じ初期化コードがさらに増える

## やるべきこと
- [ ] `AppContext` または依存性コンテナを導入し、設定・DB・外部クライアントの生成を集約する
- [ ] `ResearchService` / `ListingService` / `OrderService` / `MessageService` のようなユースケース層を追加する
- [ ] `Database` に詳細取得・集計用の専用メソッドを追加する
  - `get_candidate_by_id()`
  - `get_order_by_id()`
  - `count_candidates_by_status()`
  - `count_orders_by_status()`
- [ ] `api.py` と `cli.py` は入力検証とレスポンス整形だけを担当する薄い層にする
- [ ] 将来の Scheduler からも同じユースケース層を呼ぶ構造に揃える

## 優先度
**高** — 機能追加時の変更波及を抑える基盤整理

## 関連ファイル
- `src/ec_hub/api.py`
- `src/ec_hub/cli.py`
- `src/ec_hub/db/database.py`
- `src/ec_hub/modules/*.py`
- `src/ec_hub/services/*.py`
