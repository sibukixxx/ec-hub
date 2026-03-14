"""ダッシュボード集計ユースケース."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ec_hub.modules.profit_tracker import ProfitTracker

if TYPE_CHECKING:
    from ec_hub.context import AppContext
    from ec_hub.models import ProfitBreakdown

logger = logging.getLogger(__name__)


class DashboardService:
    """ダッシュボードの集計・利益計算を提供する."""

    def __init__(self, ctx: AppContext) -> None:
        self._ctx = ctx
        self._tracker = ProfitTracker(ctx.db, ctx.settings, ctx.fee_rules)

    async def get_dashboard_summary(self) -> dict:
        """ダッシュボード用の集計データを取得する."""
        candidate_counts = await self._ctx.db.count_candidates_by_status()
        order_counts = await self._ctx.db.count_orders_by_status()
        total_profit = await self._ctx.db.get_total_completed_profit()
        fx_rate = await self._tracker.get_fx_rate()

        return {
            "candidates": {
                "pending": candidate_counts.get("pending", 0),
                "approved": candidate_counts.get("approved", 0),
                "listed": candidate_counts.get("listed", 0),
            },
            "orders": {
                "awaiting_purchase": order_counts.get("awaiting_purchase", 0),
                "shipped": order_counts.get("shipped", 0),
                "completed": order_counts.get("completed", 0),
            },
            "recent_profit": total_profit,
            "fx_rate": fx_rate,
        }

    async def calc_profit(
        self,
        *,
        cost_jpy: int,
        ebay_price_usd: float,
        weight_g: int = 500,
        destination: str = "US",
    ) -> ProfitBreakdown:
        """利益シミュレーションを行う."""
        fx_rate = await self._tracker.get_fx_rate()
        return self._tracker.calc_net_profit(
            jpy_cost=cost_jpy,
            ebay_price_usd=ebay_price_usd,
            weight_g=weight_g,
            destination=destination,
            fx_rate=fx_rate,
        )
