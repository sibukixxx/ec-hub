# Issue #007: eBay スクレイパーの耐障害性向上 - TODO

## フェーズ1: セレクタの外部設定化

- [x] [RED] SelectorConfig モデルとローダーのテスト作成
- [x] [GREEN] SelectorConfig モデルとローダーの実装
- [x] [REFACTOR] SelectorConfig のリファクタリング
- [x] [RED] EbayScraper のセレクタ外部設定対応テスト作成
- [x] [GREEN] EbayScraper のセレクタ外部設定対応実装
- [x] [REFACTOR] EbayScraper のリファクタリング

## フェーズ2: サーキットブレーカーパターンの導入

- [x] [RED] CircuitBreaker のテスト作成
- [x] [GREEN] CircuitBreaker の実装
- [x] [REFACTOR] CircuitBreaker のリファクタリング
- [x] [RED] EbayScraper へのサーキットブレーカー統合テスト作成
- [x] [GREEN] EbayScraper へのサーキットブレーカー統合実装
- [x] [REFACTOR] サーキットブレーカー統合のリファクタリング

## フェーズ3: パース失敗アラート通知 + 妥当性チェック

- [x] [RED] ScrapeValidator のテスト作成
- [x] [GREEN] ScrapeValidator の実装
- [x] [REFACTOR] ScrapeValidator のリファクタリング
- [x] [RED] EbayScraper への通知・バリデーション統合テスト作成
- [x] [GREEN] EbayScraper への通知・バリデーション統合実装
- [x] [REFACTOR] 統合のリファクタリング
