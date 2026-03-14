"""注文管理ユースケース."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ec_hub.modules.order_manager import OrderManager

if TYPE_CHECKING:
    from ec_hub.context import AppContext

logger = logging.getLogger(__name__)


class OrderService:
    """注文の管理を提供する."""

    def __init__(self, ctx: AppContext) -> None:
        self._ctx = ctx
        self._manager = OrderManager(ctx.db, ctx.settings, ctx.fee_rules)

    async def get_orders(
        self, status: str | None = None, limit: int = 50
    ) -> list[dict]:
        """注文一覧を取得する."""
        return await self._ctx.db.get_orders(status=status, limit=limit)

    async def get_order(self, order_id: int) -> dict | None:
        """IDで注文を1件取得する."""
        return await self._ctx.db.get_order_by_id(order_id)

    async def check_new_orders(self) -> list[dict]:
        """eBay APIから新規注文を確認する."""
        return await self._manager.check_new_orders()

    async def register_order(self, **kwargs: object) -> int:
        """新規注文を登録する."""
        return await self._manager.register_order(**kwargs)

    async def mark_purchased(self, order_id: int, actual_cost_jpy: int) -> None:
        """仕入れ完了を記録する."""
        await self._manager.mark_purchased(order_id, actual_cost_jpy)

    async def mark_shipped(
        self,
        order_id: int,
        tracking_number: str,
        shipping_cost_jpy: int,
        *,
        shipping_carrier: str = "JP_POST",
    ) -> None:
        """発送完了を記録する."""
        await self._manager.mark_shipped(
            order_id, tracking_number, shipping_cost_jpy,
            shipping_carrier=shipping_carrier,
        )

    async def complete_order(self, order_id: int) -> None:
        """注文を完了する."""
        await self._manager.complete_order(order_id)

    async def close(self) -> None:
        """リソースを解放する."""
        await self._manager.close()
