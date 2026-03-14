# Issue #003: 設定スキーマの型安全化と起動時バリデーション

## 概要
このシステムは eBay / Amazon / 楽天 / Yahoo! / DeepL / Claude / LINE など外部依存が多い。
現状は設定をすべて `dict` として扱っており、キー揺れや設定漏れが「静かに機能劣化する」方向で表面化する。

## 現状
- `load_settings()` / `load_fee_rules()` は生の `dict` を返す
- モジュールごとにデフォルト値や期待キーが分散している
- `config/settings.yaml` は `claude.model` だが、`Messenger` は `classifier_model` を読みにいく
- API キー未設定時に warning だけで処理継続する箇所が多く、運用時に気付きにくい

## やるべきこと
- [x] Pydantic Settings / Pydantic Models で設定スキーマを定義する
- [x] `settings.yaml` / `settings.local.yaml` / 環境変数の優先順位を明確化する
- [x] 外部連携ごとに必須項目と optional 項目を定義し、起動時に検証する
- [x] 無効設定時は fail fast か degraded mode かを明示的に分ける
- [x] DB パス・モデル保存先・静的ファイルパスなどのパス解決を設定層に集約する

## 優先度
**高** — 多数の外部連携を安全に扱うための前提整備

## 関連ファイル
- `src/ec_hub/config.py`
- `config/settings.yaml`
- `config/fee_rules.yaml`
- `src/ec_hub/modules/*.py`
- `src/ec_hub/services/*.py`

## 残課題
- 環境変数オーバーライドは `EC_HUB_<SECTION>__<KEY>` の2階層までで、`scheduler.researcher.cron` のような深いネスト設定を直接上書きできない
- 必須/任意サービスの判定と fail fast は `AppContext.create(validate_services=True)` を使う API 起動時では有効だが、CLI など他の入口では同じ起動時検証を強制していない
- DB パスは設定層で解決するようになった一方、価格モデル保存先 (`models/price_model.pkl`) や静的ファイルパス (`api.py:STATIC_DIR`) はまだ設定層へ集約されていない
