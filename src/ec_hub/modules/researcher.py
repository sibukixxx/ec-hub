"""リサーチモジュール.

仕様書 §4.1 に基づくリサーチ自動化。
eBayの売れ筋を検索し、Amazon/楽天の仕入れ価格と比較して利益率30%以上の候補を抽出する。

処理フロー:
1. eBayで売れ筋商品を検索
2. 各商品タイトルでAmazon PA-API / 楽天APIを横断検索
3. 仕入れ価格が見つかった場合、calc_net_profit() で純利益を計算
4. 利益率30%以上 → candidatesテーブルに登録
5. LINE通知で候補件数を送信
"""

from __future__ import annotations

import asyncio
import logging

from ec_hub.config import load_fee_rules, load_settings
from ec_hub.db import Database
from ec_hub.modules.matcher import DEFAULT_MATCH_THRESHOLD, calc_match_score, is_good_match
from ec_hub.modules.notifier import Notifier
from ec_hub.modules.price_predictor import PricePredictor
from ec_hub.modules.profit_tracker import ProfitTracker
from ec_hub.scrapers.amazon import AmazonClient
from ec_hub.scrapers.base import SourceProduct, SourceSearcher
from ec_hub.scrapers.ebay import EbayScraper
from ec_hub.scrapers.muji import MujiClient
from ec_hub.scrapers.rakuten import RakutenClient
from ec_hub.scrapers.yahoo_shopping import YahooShoppingClient

logger = logging.getLogger(__name__)


class Researcher:
    """eBay ⇔ 日本ECサイトの価格差リサーチ."""

    def __init__(
        self,
        db: Database,
        settings: dict | None = None,
        fee_rules: dict | None = None,
    ) -> None:
        self._db = db
        self._settings = settings or load_settings()
        self._fee_rules = fee_rules or load_fee_rules()
        self._research_config = self._settings.get("research", {})
        self._profit_tracker = ProfitTracker(db, self._settings, self._fee_rules)
        self._notifier = Notifier(self._settings)
        self._price_predictor = PricePredictor(db)

    @property
    def min_margin_rate(self) -> float:
        return self._research_config.get("min_margin_rate", 0.30)

    @property
    def exclude_categories(self) -> list[str]:
        return self._research_config.get("exclude_categories", [])

    @property
    def max_candidates_per_run(self) -> int:
        return self._research_config.get("max_candidates_per_run", 50)

    def _create_source_searchers(self) -> list[SourceSearcher]:
        """設定に基づいて仕入れ検索クライアントを生成する."""
        searchers: list[SourceSearcher] = []

        amazon_config = self._settings.get("amazon", {})
        if amazon_config.get("access_key"):
            searchers.append(AmazonClient(
                access_key=amazon_config["access_key"],
                secret_key=amazon_config.get("secret_key", ""),
                partner_tag=amazon_config.get("partner_tag", ""),
                country=amazon_config.get("country", "www.amazon.co.jp"),
            ))

        rakuten_config = self._settings.get("rakuten", {})
        if rakuten_config.get("app_id"):
            searchers.append(RakutenClient(
                app_id=rakuten_config["app_id"],
            ))

        yahoo_config = self._settings.get("yahoo_shopping", {})
        if yahoo_config.get("app_id"):
            searchers.append(YahooShoppingClient(
                app_id=yahoo_config["app_id"],
            ))

        # Muji (no API key required, scraping-based)
        muji_config = self._settings.get("muji", {})
        if muji_config.get("enabled", False):
            searchers.append(MujiClient())

        return searchers

    async def search_ebay_sold(self, query: str, pages: int = 1) -> list[dict]:
        """eBayで販売済みリストを検索し候補を収集する."""
        candidates = []
        async with EbayScraper() as scraper:
            for page in range(1, pages + 1):
                result = await scraper.search(query, page=page, sort="date_desc")
                for product in result.products:
                    if product.category and product.category in self.exclude_categories:
                        continue
                    if product.price is None or product.price <= 0:
                        continue
                    candidates.append({
                        "item_id": product.item_id,
                        "title": product.title,
                        "price_usd": product.price,
                        "category": product.category,
                        "image_url": product.image_url,
                        "url": product.url,
                    })
        logger.info("eBay検索 '%s': %d 件取得", query, len(candidates))
        return candidates

    async def find_source_price(
        self,
        query: str,
        searchers: list[SourceSearcher],
        *,
        max_results: int = 5,
        ebay_title: str | None = None,
        ebay_price_usd: float | None = None,
        ebay_category: str | None = None,
    ) -> tuple[SourceProduct | None, dict | None]:
        """Amazon / 楽天を横断検索し、最良の仕入れ商品を見つける.

        各仕入れサイトを並行検索し、マッチスコアが閾値を超えた最良候補を返す。
        ebay_title が指定されない場合は従来通り最安商品を返す（後方互換）。

        Returns:
            (SourceProduct, match_result) or (None, None)
        """
        if not searchers:
            return None, None

        tasks = [searcher.search(query, max_results=max_results) for searcher in searchers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_products: list[SourceProduct] = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning("仕入れ検索エラー: %s", result)
                continue
            for product in result.products:
                if product.availability and product.price_jpy > 0:
                    all_products.append(product)

        if not all_products:
            return None, None

        # Match scoring when eBay title is available
        if ebay_title:
            fx_rate_val = self._settings.get("exchange_rate", {}).get("fallback_rate", 150.0)
            threshold = self._research_config.get("match_threshold", DEFAULT_MATCH_THRESHOLD)
            best_product = None
            best_match = None
            best_score = -1

            for product in all_products:
                match_result = calc_match_score(
                    ebay_title,
                    product.title,
                    ebay_price_usd=ebay_price_usd,
                    source_price_jpy=product.price_jpy,
                    fx_rate=fx_rate_val,
                    ebay_category=ebay_category,
                    source_category=product.category,
                )
                if is_good_match(match_result, threshold) and match_result["score"] > best_score:
                    best_score = match_result["score"]
                    best_product = product
                    best_match = match_result

            if best_product:
                logger.debug(
                    "マッチ成功: %s → %s (score=%d)",
                    ebay_title[:30], best_product.title[:30], best_score,
                )
                return best_product, best_match
            else:
                logger.debug("マッチ閾値未達: %s (最高スコア=%d)", ebay_title[:30], best_score)
                return None, None

        # Fallback: return cheapest (backward compatibility)
        cheapest = min(all_products, key=lambda p: p.price_jpy)
        return cheapest, None

    async def evaluate_candidate(
        self,
        *,
        item_code: str,
        source_site: str,
        title_jp: str,
        cost_jpy: int,
        ebay_price_usd: float,
        weight_g: int = 500,
        destination: str = "US",
        category: str | None = None,
        image_url: str | None = None,
        source_url: str | None = None,
        match_score: int | None = None,
        match_reason: str | None = None,
    ) -> int | None:
        """候補商品を評価し、基準を満たせばDBに登録する.

        Returns:
            登録した candidate の ID、または基準未達の場合 None
        """
        fx_rate = await self._profit_tracker.get_fx_rate()
        breakdown = self._profit_tracker.calc_net_profit(
            jpy_cost=cost_jpy,
            ebay_price_usd=ebay_price_usd,
            weight_g=weight_g,
            destination=destination,
            fx_rate=fx_rate,
        )

        # 送料が売価の50%超は除外
        max_shipping_ratio = self._research_config.get("max_shipping_ratio", 0.50)
        if breakdown.jpy_revenue > 0 and breakdown.shipping_cost / breakdown.jpy_revenue > max_shipping_ratio:
            logger.debug(
                "送料比率超過で除外: %s (%.1f%%)",
                title_jp, breakdown.shipping_cost / breakdown.jpy_revenue * 100,
            )
            return None

        # 利益率基準未達は除外
        if breakdown.margin_rate < self.min_margin_rate:
            logger.debug("利益率不足で除外: %s (%.1f%%)", title_jp, breakdown.margin_rate * 100)
            return None

        candidate_id = await self._db.add_candidate(
            item_code=item_code,
            source_site=source_site,
            title_jp=title_jp,
            title_en=None,
            cost_jpy=cost_jpy,
            ebay_price_usd=ebay_price_usd,
            net_profit_jpy=breakdown.net_profit,
            margin_rate=breakdown.margin_rate,
            weight_g=weight_g,
            category=category,
            image_url=image_url,
            source_url=source_url,
            match_score=match_score,
            match_reason=match_reason,
        )
        # ML prediction for additional insight
        prediction_info = ""
        if self._price_predictor.is_trained:
            pred = self._price_predictor.predict(
                cost_jpy=cost_jpy, weight_g=weight_g,
                source_site=source_site, category=category, fx_rate=fx_rate,
            )
            prediction_info = f" | ML予測: ${pred.predicted_price_usd:.0f} (信頼度{pred.confidence:.0%})"

        logger.info(
            "候補登録: %s | 仕入¥%d → eBay$%.0f | 利益 ¥%d (%.0f%%) [%s]%s",
            title_jp[:30], cost_jpy, ebay_price_usd,
            breakdown.net_profit, breakdown.margin_rate * 100,
            source_site, prediction_info,
        )
        return candidate_id

    async def research_single(
        self,
        ebay_product: dict,
        searchers: list[SourceSearcher],
    ) -> int | None:
        """単一のeBay商品に対してリサーチを実行する.

        1. eBay商品タイトルで仕入れサイトを横断検索
        2. 最安の仕入れ価格を見つける
        3. 利益計算して基準を満たせばDBに登録

        Returns:
            登録した candidate の ID、または None
        """
        title = ebay_product.get("title", "")
        price_usd = ebay_product.get("price_usd")
        if not title or not price_usd:
            return None

        # タイトルから検索クエリを生成
        search_query = simplify_search_query(title)

        source_product, match_result = await self.find_source_price(
            search_query,
            searchers,
            ebay_title=title,
            ebay_price_usd=price_usd,
            ebay_category=ebay_product.get("category"),
        )
        if not source_product:
            logger.debug("仕入れ先なし: %s", title[:40])
            return None

        # Build match reason string
        match_score_val = match_result["score"] if match_result else None
        match_reason = " / ".join(match_result["reasons"]) if match_result and match_result["reasons"] else None

        return await self.evaluate_candidate(
            item_code=source_product.item_code,
            source_site=source_product.source_site,
            title_jp=source_product.title,
            cost_jpy=source_product.price_jpy,
            ebay_price_usd=price_usd,
            weight_g=source_product.weight_g or 500,
            category=source_product.category or ebay_product.get("category"),
            image_url=source_product.image_url,
            source_url=source_product.url,
            match_score=match_score_val,
            match_reason=match_reason,
        )

    async def run(self, queries: list[str] | None = None, *, pages: int = 1) -> int:
        """リサーチ処理を実行する.

        処理フロー:
        1. eBayで各キーワードの売れ筋を検索
        2. 各eBay商品に対してAmazon/楽天で仕入れ価格を検索
        3. 利益率30%以上の商品を候補として登録
        4. LINE通知で結果を報告

        Args:
            queries: 検索キーワードリスト
            pages: eBay検索のページ数

        Returns:
            登録した候補数
        """
        if not queries:
            queries = ["japanese vintage", "anime figure", "japan exclusive"]

        # Load or train price prediction model
        if not self._price_predictor.load():
            await self._price_predictor.train(min_samples=5)

        searchers = self._create_source_searchers()
        if not searchers:
            logger.warning(
                "仕入れ検索APIが未設定です。"
                "config/settings.yaml の amazon / rakuten セクションにAPIキーを設定してください。"
            )
            for query in queries:
                ebay_results = await self.search_ebay_sold(query, pages=pages)
                logger.info("'%s': eBay %d 件取得（仕入れ検索はスキップ）", query, len(ebay_results))
            return 0

        total_registered = 0
        try:
            for query in queries:
                if total_registered >= self.max_candidates_per_run:
                    logger.info("最大候補数 (%d) に到達。リサーチ終了。", self.max_candidates_per_run)
                    break

                ebay_results = await self.search_ebay_sold(query, pages=pages)
                logger.info("'%s': eBay %d 件を仕入れ検索中...", query, len(ebay_results))

                for ebay_product in ebay_results:
                    if total_registered >= self.max_candidates_per_run:
                        break
                    candidate_id = await self.research_single(ebay_product, searchers)
                    if candidate_id is not None:
                        total_registered += 1
        finally:
            for searcher in searchers:
                await searcher.close()

        logger.info("リサーチ完了: %d 件の候補を登録", total_registered)

        if total_registered > 0:
            await self._notifier.notify_candidates(total_registered)

        return total_registered


def simplify_search_query(title: str) -> str:
    """eBayの商品タイトルから検索クエリを生成する.

    長いタイトルから不要な修飾語を除去し、
    日本ECサイトでの検索精度を上げる。
    """
    noise_words = {
        "new", "used", "rare", "vintage", "authentic", "genuine",
        "brand", "sealed", "nib", "nip", "mint", "excellent",
        "free", "shipping", "fast", "ship", "from", "japan",
        "us", "seller", "lot", "set", "bundle",
    }
    words = title.split()
    filtered = [w for w in words if w.lower().strip("!,.()-[]") not in noise_words]

    # 最大6語に制限
    return " ".join(filtered[:6])
