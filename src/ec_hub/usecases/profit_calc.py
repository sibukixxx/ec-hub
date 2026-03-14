"""Profit calculation use case."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ec_hub.modules.profit_tracker import ProfitTracker

if TYPE_CHECKING:
    from ec_hub.context import AppContext


class ProfitCalcUseCase:
    """Profit calculation orchestration."""

    def __init__(self, ctx: AppContext) -> None:
        self._ctx = ctx

    async def calculate(
        self,
        cost_jpy: int,
        ebay_price_usd: float,
        weight_g: int = 500,
        destination: str = "US",
    ) -> dict:
        tracker = ProfitTracker(self._ctx.db, self._ctx.settings, self._ctx.fee_rules)
        fx_rate = await tracker.get_fx_rate()
        breakdown = tracker.calc_net_profit(
            jpy_cost=cost_jpy,
            ebay_price_usd=ebay_price_usd,
            weight_g=weight_g,
            destination=destination,
            fx_rate=fx_rate,
        )
        return {
            "jpy_cost": breakdown.jpy_cost,
            "ebay_price_usd": breakdown.ebay_price_usd,
            "fx_rate": breakdown.fx_rate,
            "jpy_revenue": breakdown.jpy_revenue,
            "ebay_fee": breakdown.ebay_fee,
            "payoneer_fee": breakdown.payoneer_fee,
            "shipping_cost": breakdown.shipping_cost,
            "packing_cost": breakdown.packing_cost,
            "fx_buffer": breakdown.fx_buffer,
            "total_cost": breakdown.total_cost,
            "net_profit": breakdown.net_profit,
            "margin_rate": breakdown.margin_rate,
        }
