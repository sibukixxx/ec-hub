# Issue #008: マッチングエンジン改善 - TODO

## フェーズ1: レビュー/在庫情報のスコア反映

- [x] [RED] calc_match_score にレビュー/在庫スコアのテスト作成
- [x] [GREEN] calc_match_score にレビュー/在庫スコアの実装
- [x] [REFACTOR] レビュー/在庫スコアのリファクタリング

## フェーズ2: simplify_search_query の高度化

- [x] [RED] simplify_search_query のブランド+型番優先テスト作成
- [x] [GREEN] simplify_search_query の高度化実装
- [x] [REFACTOR] simplify_search_query のリファクタリング

## フェーズ3: フロントエンド - Candidates 画面にマッチ情報表示

- [x] [GREEN] Candidates.jsx に match_score / match_reason カラム追加

## フェーズ4: フロントエンド - Compare 画面にマッチ情報表示

- [x] [GREEN] Compare.jsx にマッチ根拠表示追加
