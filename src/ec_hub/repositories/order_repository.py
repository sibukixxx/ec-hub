"""Order repository."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ec_hub.db import Database


class OrderRepository:
    """Orders table access."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def get_by_id(self, order_id: int) -> dict | None:
        return await self._db.get_order_by_id(order_id)

    async def list(self, status: str | None = None, limit: int = 50) -> list[dict]:
        return await self._db.get_orders(status=status, limit=limit)

    async def add(self, **kwargs: object) -> int:
        return await self._db.add_order(**kwargs)

    async def update(self, order_id: int, **fields: object) -> None:
        await self._db.update_order(order_id, **fields)

    async def count_by_status(self, status: str | None = None) -> int:
        return await self._db.count_orders_by_status(status)
