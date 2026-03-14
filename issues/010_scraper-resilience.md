# Issue #010: eBay スクレイパーの耐障害性向上

## 概要
CSS セレクタに依存した HTML パースのため、eBay の DOM 変更で壊れるリスクがある。

## 現状
- BeautifulSoup + lxml で HTML パース
- 固定の CSS セレクタで要素取得
- リトライ（指数バックオフ）はあるがサーキットブレーカーなし

## やるべきこと
- [x] セレクタの外部設定化（YAML or JSON）で変更時に再デプロイ不要に
  - `config/selectors.yaml` に全セレクタを外部化
  - `src/ec_hub/scrapers/selectors.py` で読み込み (Pydantic モデル)
- [x] サーキットブレーカーパターンの導入（連続失敗時にスクレイピング停止）
  - `src/ec_hub/scrapers/circuit_breaker.py` に CLOSED→OPEN→HALF_OPEN の状態遷移を実装
  - `search()` / `get_item()` で自動的にブレーカーを作動
- [x] パース失敗時のアラート通知（LINE）
  - `_notify_parse_issues()` で LINE 通知連携
  - Notifier をオプション引数として注入可能
- [x] スクレイピング結果の妥当性チェック（0件結果の検知等）
  - `validate_result()` メソッド: 0件パース検知、全件価格null検知
- [ ] eBay API (Finding API) への段階的移行検討
  - eBay Finding API は 2024 年に廃止済み。Browse API への移行を検討する
  - 移行時は `EbayApiClient` (services/ebay_api.py) を拡張し、スクレイパーと同じインターフェースを提供する
  - 当面はスクレイパー + セレクタ外部設定で運用

## 優先度
**低** — 現状動作しているが、長期運用で問題になる

## 関連ファイル
- `src/ec_hub/scrapers/ebay.py`
- `src/ec_hub/scrapers/base.py`
- `src/ec_hub/scrapers/circuit_breaker.py` (新規)
- `src/ec_hub/scrapers/selectors.py` (新規)
- `config/selectors.yaml` (新規)
- `tests/test_circuit_breaker.py` (新規)
- `tests/test_scraper_resilience.py` (新規)
