# Issue #010: pnpm 移行後のクリーンアップ

## 概要
npm → pnpm への移行は完了。残りの整備事項。

## 状態
- [x] package-lock.json 削除
- [x] pnpm-lock.yaml 生成
- [x] esbuild の onlyBuiltDependencies 設定
- [x] .gitignore に package-lock.json 追加
- [x] ビルド動作確認

## 残タスク
- [ ] README.md のコマンド例を `pnpm` に統一（該当箇所があれば）
- [ ] CI/CD パイプラインがあれば pnpm に変更

## 優先度
**低** — 基本完了済み

## 関連ファイル
- `frontend/package.json`
- `frontend/pnpm-lock.yaml`
