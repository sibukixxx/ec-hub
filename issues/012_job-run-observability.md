# Issue #012: ジョブ実行履歴と運用監視の追加

## 概要
このシステムは外部 API・スクレイピング・スケジュール実行への依存が強く、
実運用では「何が成功し、どこで degraded になっているか」を時系列で見える化しないと保守できない。
現在はログ出力と LINE 通知だけで、運用履歴が残らない。

## 現状
- `Researcher.run()` / `Lister.run()` / `OrderManager.run()` / `Messenger.run()` は処理件数を返すだけ
- ジョブ実行時間・失敗理由・再試行回数・入力パラメータが残らない
- 為替フォールバック、翻訳 API 未設定、eBay API 未設定などの degraded 状態が UI に出ない
- Scheduler の有無は issue #014 で扱っているが、履歴・監視は未着手

## やるべきこと
- [ ] `job_runs` テーブルを追加し、各ジョブの開始・終了・結果を保存する
- [ ] `integration_status` または `system_health` を持ち、外部連携の可用性を記録する
- [ ] 各モジュール実行を共通 wrapper で包み、処理件数・warning・error を記録する
- [ ] Dashboard に直近実行履歴と障害状態を表示する
- [ ] LINE 通知は重大障害のみ送るよう severity / dedupe 制御を入れる

## 優先度
**中** — 自動運用を始める段階で必須になる運用基盤

## 関連ファイル
- `src/ec_hub/api.py`
- `src/ec_hub/modules/*.py`
- `src/ec_hub/db/database.py`
- `frontend/src/pages/Dashboard.jsx`

## 残課題
- `research_runs` はあるが、全ジョブ共通の `job_runs` / `system_health` は未実装
- `Researcher` / `Lister` / `OrderManager` / `Messenger` を共通 wrapper で包む実行記録、warning、error 集約がない
- Dashboard の実行履歴表示と、LINE 通知の severity / dedupe 制御が未実装
