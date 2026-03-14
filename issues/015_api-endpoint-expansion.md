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
- [ ] `GET /api/research/status` — リサーチ実行状況 (非同期ジョブ管理が必要。将来対応)
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

## 残課題
- `POST /api/research/run` はあるが、非同期ジョブ前提の `GET /api/research/status` は未実装
- 代わりに `GET /api/research/runs` / `GET /api/research/runs/{id}` はあるため、今後は専用 status API を足すか既存の履歴 API に役割を寄せるかを整理する必要がある
