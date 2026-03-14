# Issue #010: pnpm 移行後のクリーンアップ

## 概要
npm → pnpm への移行は完了。残りの整備事項。

## 状態
- [x] package-lock.json 削除
- [x] pnpm-lock.yaml 生成
- [x] esbuild の onlyBuiltDependencies 設定
- [x] .gitignore に package-lock.json 追加
- [x] ビルド動作確認

## 完了確認
- [x] README.md のフロントエンドコマンド例は `pnpm` に統一済み
- [x] CI/CD パイプラインはリポジトリ内に存在せず、追加変更不要

## 優先度
**低** — 完了

## 関連ファイル
- `frontend/package.json`
- `frontend/pnpm-lock.yaml`
