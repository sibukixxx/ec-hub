# Issue #018: `uv` 前提の開発環境整備と Docker 化

## 概要
README と `CLAUDE.md` は `uv` 前提で記述されているが、現状の実行環境では `uv` や `pytest` が未導入でも詰まりやすい。
開発者ごとの差異を減らすため、`uv` の導入手順を明確化するか、Docker で再現可能な開発環境を用意したい。

## 現状
- ドキュメントは `uv sync` / `uv run ...` 前提
- この環境では `uv` が見つからず、テスト実行もできなかった
- Dockerfile / docker-compose.yml / devcontainer 設定は未整備
- バックエンドとフロントエンドの起動前提がローカル依存

## やるべきこと
- [ ] `uv` の導入手順を README に追加する
  - macOS
  - Linux
  - Windows
- [ ] `uv sync` だけでバックエンドが動く前提を検証する
- [ ] Docker ベースでの開発手段を追加する
  - `Dockerfile`
  - `docker-compose.yml`
  - 必要なら `frontend` 用サービス
- [ ] コンテナ内で `uv run pytest` / `uv run uvicorn ...` / `pnpm dev` が実行できるようにする
- [ ] `.dockerignore` とローカル DB / 設定ファイルのマウント方針を整理する

## 優先度
**中** — オンボーディングと検証再現性の改善

## 関連ファイル
- `README.md`
- `CLAUDE.md`
- `pyproject.toml`
- `frontend/package.json`
