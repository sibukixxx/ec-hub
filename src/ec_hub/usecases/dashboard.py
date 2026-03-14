"""Dashboard use case."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ec_hub.modules.profit_tracker import ProfitTracker

if TYPE_CHECKING:
    from ec_hub.context import AppContext


class DashboardUseCase:
    """Dashboard summary aggregation."""

    def __init__(self, ctx: AppContext) -> None:
        self._ctx = ctx

    async def get_summary(self) -> dict:
        candidates = self._ctx.candidates
        orders = self._ctx.orders

        pending = await candidates.count_by_status("pending")
        approved = await candidates.count_by_status("approved")
        listed = await candidates.count_by_status("listed")

        awaiting = await orders.count_by_status("awaiting_purchase")
        shipped = await orders.count_by_status("shipped")
        completed = await orders.count_by_status("completed")

        # Calculate recent profit from completed orders
        completed_orders = await orders.list(status="completed", limit=1000)
        total_profit = sum(o.get("net_profit_jpy", 0) or 0 for o in completed_orders)

        tracker = ProfitTracker(self._ctx.db, self._ctx.settings, self._ctx.fee_rules)
        fx_rate = await tracker.get_fx_rate()

        recent_jobs = await self._ctx.db.get_job_runs(limit=5)
        health = await self._ctx.db.get_all_integration_status()

        return {
            "candidates": {
                "pending": pending,
                "approved": approved,
                "listed": listed,
            },
            "orders": {
                "awaiting_purchase": awaiting,
                "shipped": shipped,
                "completed": completed,
            },
            "recent_profit": total_profit,
            "fx_rate": fx_rate,
            "recent_jobs": recent_jobs,
            "health": health,
        }
