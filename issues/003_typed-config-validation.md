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
- [x] `settings.yaml` に対する `settings.local.yaml` の重ね合わせと、`settings.yaml` < `settings.local.yaml` < 環境変数 の優先順位整理 → `config.py` の `_deep_merge` + `load_settings` で実装済み
- [x] 外部連携ごとの「必須なら起動失敗」「任意なら degraded mode」の区分 → `Settings.validate_required_services()` + `AppContext.create(validate_services=True)` で実装済み
- [x] DB パスのパス解決を設定層に集約 → `Settings.resolve_paths()` + `DatabaseConfig.resolved_path` で実装済み
- 静的ファイルパス (`api.py:STATIC_DIR`) は現状ハードコードのまま（設定で変更する需要が低いため据え置き）
