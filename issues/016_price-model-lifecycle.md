# Issue #016: 価格予測モデルの学習データ設計と運用分離

## 概要
価格予測はこのシステムの差別化要素になり得るが、
現状は live の API リクエスト中に学習を走らせる可能性があり、学習データも `candidates` 中心で粗い。
業務運用に載せるにはモデルのライフサイクル管理が必要。

## 現状
- `/api/compare` と `/api/predict/price` がモデル未学習時にその場で学習しうる
- 学習対象が `candidates` テーブルのみで、`pending` も含まれる
- pickle 保存はあるが、モデル version・学習日時・サンプル数・評価指標の管理がない
- 予測結果が「ML 推定なのかルールベースなのか」を運用者が把握しづらい

## やるべきこと
- [ ] 学習データを `approved` / `listed` / `completed` など信頼できる状態に限定する
- [ ] モデルメタデータを保存する
  - version
  - trained_at
  - sample_count
  - score
  - feature schema
- [ ] 学習処理をリクエスト経路から外し、Scheduler または管理 API の明示操作に寄せる
- [ ] 推論レスポンスに `prediction_source` (`ml` / `rule_based`) を含める
- [ ] 低品質モデルを自動で無効化する閾値を設ける

## 優先度
**中** — 機能はあるが、運用品質を上げるには設計見直しが必要

## 関連ファイル
- `src/ec_hub/modules/price_predictor.py`
- `src/ec_hub/api.py`
- `src/ec_hub/db/database.py`
- `tests/test_price_predictor.py`
