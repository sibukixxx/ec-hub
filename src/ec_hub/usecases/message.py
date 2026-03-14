"""Message use case."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ec_hub.exceptions import NotFoundError

if TYPE_CHECKING:
    from ec_hub.context import AppContext


class MessageUseCase:
    """Message management orchestration."""

    def __init__(self, ctx: AppContext) -> None:
        self._ctx = ctx

    async def list_messages(
        self, buyer_username: str | None = None, limit: int = 50
    ) -> list[dict]:
        return await self._ctx.messages.list(buyer_username=buyer_username, limit=limit)

    async def reply(self, message_id: int, body: str) -> dict:
        original = await self._ctx.messages.get_by_id(message_id)
        if not original:
            raise NotFoundError("Message", message_id)

        reply_id = await self._ctx.messages.add(
            buyer_username=original["buyer_username"],
            body=body,
            direction="outbound",
            order_id=original.get("order_id"),
            category=original.get("category"),
        )
        return {
            "id": reply_id,
            "buyer_username": original["buyer_username"],
            "direction": "outbound",
            "body": body,
        }
