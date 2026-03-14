"""Listing use case."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ec_hub.modules.job_runner import JobRunner
from ec_hub.modules.lister import Lister
from ec_hub.modules.profit_tracker import ProfitTracker

if TYPE_CHECKING:
    from ec_hub.context import AppContext


class ListingUseCase:
    """eBay listing orchestration."""

    def __init__(self, ctx: AppContext) -> None:
        self._ctx = ctx

    async def run(self, candidate_ids: list[int] | None = None) -> int:
        lister = Lister(self._ctx.db, self._ctx.settings, self._ctx.fee_rules)

        async def _execute() -> int:
            try:
                if candidate_ids:
                    return await lister.run_selected(candidate_ids)
                return await lister.run()
            finally:
                await lister.close()

        runner = JobRunner(self._ctx.db)
        return await runner.run("listing", _execute)

    async def preview(self, candidate_id: int) -> dict | None:
        """出品プレビュー情報を生成する（実際には出品しない）."""
        candidate = await self._ctx.candidates.get_by_id(candidate_id)
        if not candidate:
            return None

        lister = Lister(self._ctx.db, self._ctx.settings, self._ctx.fee_rules)
        tracker = ProfitTracker(self._ctx.db, self._ctx.settings, self._ctx.fee_rules)
        try:
            fx_rate = await tracker.get_fx_rate()
            cost_jpy = candidate.get("cost_jpy", 0)
            weight_g = candidate.get("weight_g") or 500
            listing_price = lister.calc_listing_price(cost_jpy, weight_g, fx_rate)

            fee_rules = self._ctx.fee_rules
            ebay_rate = fee_rules.get("ebay_fees", {}).get("default_rate", 0.1325)
            payoneer_rate = fee_rules.get("payoneer", {}).get("rate", 0.02)
            packing_cost = fee_rules.get("packing", {}).get("default_cost", 200)
            shipping_cost = tracker.calc_shipping(weight_g, "US")

            jpy_revenue = listing_price * fx_rate
            ebay_fee = int(jpy_revenue * ebay_rate)
            payoneer_fee = int(jpy_revenue * payoneer_rate)
            net_profit = int(jpy_revenue - cost_jpy - ebay_fee - payoneer_fee - shipping_cost - packing_cost)

            return {
                "candidate_id": candidate_id,
                "title_jp": candidate.get("title_jp"),
                "source_site": candidate.get("source_site"),
                "cost_jpy": cost_jpy,
                "weight_g": weight_g,
                "listing_price_usd": round(listing_price, 2),
                "fx_rate": round(fx_rate, 2),
                "ebay_fee_jpy": ebay_fee,
                "payoneer_fee_jpy": payoneer_fee,
                "shipping_cost_jpy": shipping_cost,
                "packing_cost_jpy": packing_cost,
                "estimated_profit_jpy": net_profit,
                "sku": f"ECHUB-{candidate_id}",
                "status": candidate.get("status"),
            }
        finally:
            await lister.close()

    async def check_selling_limit(self) -> dict:
        lister = Lister(self._ctx.db, self._ctx.settings, self._ctx.fee_rules)
        try:
            return await lister.check_selling_limit()
        finally:
            await lister.close()
