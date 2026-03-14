"""Message repository."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ec_hub.db import Database


class MessageRepository:
    """Messages table access."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def get_by_id(self, message_id: int) -> dict | None:
        return await self._db.get_message_by_id(message_id)

    async def list(
        self,
        buyer_username: str | None = None,
        category: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        return await self._db.get_messages(buyer_username=buyer_username, category=category, limit=limit)

    async def add(self, **kwargs: object) -> int:
        return await self._db.add_message(**kwargs)
