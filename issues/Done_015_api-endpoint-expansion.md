# Issue #015: REST API エンドポイントの拡充

## 概要
現在の API は Dashboard / Candidates / Orders / ProfitCalc のみ。
多くのモジュール機能が API から利用できない。

## 現状
- Researcher → CLI のみ、API 未公開
- Lister → CLI のみ、API 未公開
- OrderManager → API 未公開
- Messenger → API 未公開
- データエクスポート → API 未対応

## やるべきこと
- [x] `POST /api/research/run` — リサーチ手動実行
- [x] `GET /api/research/status` — `POST /api/research/run` を非同期化し、`GET /api/research/runs/{id}` で `completed_at` の有無により実行状況を確認可能に
- [x] `POST /api/listing/run` — 承認済み候補の出品実行
- [x] `GET /api/listing/limits` — eBay 出品制限確認
- [x] `POST /api/orders/check` — 新規注文チェック
- [x] `PUT /api/orders/{id}/status` — 注文ステータス更新
- [x] `GET /api/messages` — メッセージ一覧
- [x] `POST /api/messages/{id}/reply` — 手動返信
- [x] `GET /api/export/{type}` — CSV/JSON エクスポート

## 優先度
**高** — フロントエンドからの操作に必須

## 関連ファイル
- `src/ec_hub/api.py`
- `src/ec_hub/modules/*.py`

## 完了確認
- `src/ec_hub/api.py` に Research / Listing / Orders / Messages / Export の各エンドポイントが揃い、CLI 依存だった主要操作を REST API から実行できるようになった
- `POST /api/research/run` は `BackgroundTasks` で非同期実行され、`GET /api/research/runs/{run_id}` のポーリングで進捗確認できる
- `frontend/src/api.ts` に対応ラッパーが実装され、Operations / Orders / Messages 画面から実際に呼び出している
- 将来的な本格ジョブキュー導入は別テーマとして切り出せる状態になった
