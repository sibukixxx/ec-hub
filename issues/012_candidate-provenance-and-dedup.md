# Issue #012: リサーチ候補の重複排除と出所トレーサビリティ

## 概要
このシステムの中核は「eBay 売れ筋」と「国内仕入れ候補」を突き合わせて候補化することだが、
現状の `candidates` テーブルではその候補がどの eBay 商品観測とどのリサーチ実行から生まれたか追跡できない。
定期実行を始めると重複候補が蓄積しやすい。

## 現状
- `candidates` には仕入れ側の `item_code` はあるが、対応する `ebay_item_id` や `ebay_title` が保存されない
- `Researcher.run()` は毎回 `add_candidate()` するため、同一候補の再観測でも新規行が増える
- `research_runs` や候補生成ログがなく、どのクエリ・どの時点の価格で登録されたか分からない
- Dashboard / Candidates 画面でも候補の根拠を辿れない

## やるべきこと
- [ ] `research_runs` テーブルを追加し、実行時刻・クエリ・処理件数・結果件数を保存する
- [ ] `candidates` に eBay 側の出所情報を追加する
  - `ebay_item_id`
  - `ebay_title`
  - `ebay_url`
  - `research_run_id`
- [ ] 同一の `source_site + item_code + ebay_item_id` を重複登録しない一意制約または upsert を導入する
- [ ] 再観測時は新規行ではなく価格スナップショット更新にする
- [ ] API / フロントで候補詳細に「どの観測から来たか」を表示できるようにする

## 優先度
**高** — Scheduler 導入後のデータ汚染を防ぐ

## 関連ファイル
- `src/ec_hub/db/database.py`
- `src/ec_hub/models.py`
- `src/ec_hub/modules/researcher.py`
- `src/ec_hub/api.py`
- `frontend/src/pages/Candidates.jsx`
