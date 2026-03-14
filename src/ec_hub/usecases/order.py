"""Order use case."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ec_hub.exceptions import InvalidStatusError, NotFoundError
from ec_hub.modules.order_manager import OrderManager

if TYPE_CHECKING:
    from ec_hub.context import AppContext

VALID_STATUSES = {"awaiting_purchase", "purchased", "shipped", "delivered", "completed"}


class OrderUseCase:
    """Order management orchestration."""

    def __init__(self, ctx: AppContext) -> None:
        self._ctx = ctx

    async def list_orders(self, status: str | None = None, limit: int = 50) -> list[dict]:
        return await self._ctx.orders.list(status=status, limit=limit)

    async def get_order(self, order_id: int) -> dict:
        order = await self._ctx.orders.get_by_id(order_id)
        if not order:
            raise NotFoundError("Order", order_id)
        return order

    async def update_status(
        self,
        order_id: int,
        status: str,
        *,
        actual_cost_jpy: int | None = None,
        tracking_number: str | None = None,
        shipping_cost_jpy: int | None = None,
    ) -> dict:
        if status not in VALID_STATUSES:
            raise InvalidStatusError(status, VALID_STATUSES)

        # Verify order exists
        await self.get_order(order_id)

        manager = OrderManager(self._ctx.db, self._ctx.settings, self._ctx.fee_rules)
        try:
            if status == "purchased":
                await manager.mark_purchased(order_id, actual_cost_jpy or 0)
            elif status == "shipped":
                await manager.mark_shipped(
                    order_id,
                    tracking_number=tracking_number or "",
                    shipping_cost_jpy=shipping_cost_jpy or 0,
                )
            elif status == "delivered":
                await manager.mark_delivered(order_id)
            elif status == "completed":
                await manager.complete_order(order_id)
            else:
                await self._ctx.orders.update(order_id, status=status)
        finally:
            await manager.close()

        return {"id": order_id, "status": status}

    async def check_new_orders(self) -> int:
        manager = OrderManager(self._ctx.db, self._ctx.settings, self._ctx.fee_rules)
        try:
            new_orders = await manager.check_new_orders()
            for order_data in new_orders:
                await manager.register_order(**order_data)
            return len(new_orders)
        finally:
            await manager.close()
