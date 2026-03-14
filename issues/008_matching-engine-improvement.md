# Issue #008: eBay⇔仕入れ商品のマッチング精度改善

## 概要
このシステムは価格差の抽出精度が価値そのものだが、
現状は `simplify_search_query()` でタイトルを短縮し、検索結果の最安商品を採用している。
型番違い・数量違い・セット品違いでも誤って候補化するリスクが高い。

## 現状
- `simplify_search_query()` はノイズ語削除のみで、ブランド・型番・サイズ・数量の抽出がない
- `find_source_price()` は各サイト結果から「在庫あり最安」を返すだけ
- タイトル類似度、カテゴリ整合性、レビュー、画像、数量単位の照合がない
- 誤マッチしても Candidates 画面上で判断根拠が見えない

## やるべきこと
- [ ] 商品名正規化ロジックを追加する
  - ブランド
  - 型番
  - サイズ / 色
  - 数量 / セット数
- [ ] eBay 商品と仕入れ商品に対するマッチスコアを導入する
  - タイトル類似度
  - カテゴリ一致
  - 価格乖離
  - レビュー / 在庫情報
- [ ] 「最安採用」ではなく「スコア閾値を超えた最良候補採用」に変更する
- [ ] 候補データに `match_score` と `match_reason` を保存する
- [ ] Compare / Candidates 画面で一致根拠を表示する

## 優先度
**高** — 利益計算以前の候補品質を左右するコア機能

## 関連ファイル
- `src/ec_hub/modules/researcher.py`
- `src/ec_hub/scrapers/base.py`
- `src/ec_hub/models.py`
- `frontend/src/pages/Compare.jsx`
- `frontend/src/pages/Candidates.jsx`

## 残課題
- `matcher.py` による正規化・採点と `match_score` / `match_reason` 保存は入ったが、Compare / Candidates 画面に一致根拠の表示がない
- `ResearchConfig.match_threshold` の既定値は `0.6` だが、実際のスコアは `0-100` で評価しており、閾値の単位を揃える必要がある
- レビュー・在庫・画像などの追加根拠はまだスコアへ入っておらず、タイトル / 型番 / 数量 / 価格 / カテゴリ中心の判定に留まっている
