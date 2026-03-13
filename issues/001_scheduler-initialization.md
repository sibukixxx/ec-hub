# Issue #001: APScheduler の初期化・統合

## 概要
`apscheduler` が依存関係に含まれているが、実際にはどこでもインスタンス化されていない。
Researcher / OrderManager / Messenger / ProfitTracker の定期実行が動作しない。

## 現状
- `config/settings.yaml` にスケジュール設定（cron/interval）が定義済み
- 各モジュールに `run()` メソッドは実装済み
- **スケジューラが起動されないため、自動ワークフローが一切動かない**

## やるべきこと
- [ ] `api.py` の lifespan 内で APScheduler を初期化
- [ ] settings.yaml のスケジュール設定を読み込んでジョブ登録
  - Researcher: 定期リサーチ実行
  - OrderManager: 新規注文チェック
  - Messenger: 新規メッセージチェック
  - ProfitTracker: 日次レポート生成
- [ ] スケジューラの状態確認用 API エンドポイント追加 (`GET /api/scheduler/status`)
- [ ] ジョブの手動トリガー用 API エンドポイント追加 (`POST /api/scheduler/trigger/{job_name}`)

## 優先度
**高** — 自動化の根幹機能

## 関連ファイル
- `src/ec_hub/api.py`
- `config/settings.yaml`
- `src/ec_hub/modules/*.py`
