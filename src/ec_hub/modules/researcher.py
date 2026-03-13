"""リサーチモジュール.

仕様書 §4.1 に基づくリサーチ自動化。
eBayの売れ筋を検索し、日本のECサイトとの価格差を分析して候補を抽出する。
"""

from __future__ import annotations

import logging

from ec_hub.config import load_fee_rules, load_settings
from ec_hub.db import Database
from ec_hub.models import CandidateStatus
from ec_hub.modules.notifier import Notifier
from ec_hub.modules.profit_tracker import ProfitTracker
from ec_hub.scrapers.ebay import EbayScraper

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

    @property
    def min_margin_rate(self) -> float:
        return self._research_config.get("min_margin_rate", 0.30)

    @property
    def exclude_categories(self) -> list[str]:
        return self._research_config.get("exclude_categories", [])

    async def search_ebay_sold(self, query: str, pages: int = 1) -> list[dict]:
        """eBayで販売済みリストを検索し候補を収集する."""
        candidates = []
        async with EbayScraper() as scraper:
            for page in range(1, pages + 1):
                result = await scraper.search(query, page=page, sort="date_desc")
                for product in result.products:
                    if product.category and product.category in self.exclude_categories:
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
            logger.debug("送料比率超過で除外: %s (%.1f%%)", title_jp, breakdown.shipping_cost / breakdown.jpy_revenue * 100)
            return None

        # 利益率30%未満は除外
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
        )
        logger.info(
            "候補登録: %s | 利益 ¥%d (%.0f%%)",
            title_jp, breakdown.net_profit, breakdown.margin_rate * 100,
        )
        return candidate_id

    async def run(self, queries: list[str] | None = None) -> int:
        """リサーチ処理を実行する.

        Args:
            queries: 検索キーワードリスト（Noneの場合はデフォルト）

        Returns:
            登録した候補数
        """
        if not queries:
            queries = ["japanese vintage", "anime figure", "japan exclusive"]

        total_registered = 0
        for query in queries:
            ebay_results = await self.search_ebay_sold(query)
            logger.info("'%s' で %d 件を評価中...", query, len(ebay_results))
            # TODO: 各eBay商品に対してAmazon/楽天で仕入れ価格を検索し
            # evaluate_candidate() で評価する
            # 現在はeBay検索結果の収集のみ実装済み

        if total_registered > 0:
            await self._notifier.notify_candidates(total_registered)

        return total_registered
