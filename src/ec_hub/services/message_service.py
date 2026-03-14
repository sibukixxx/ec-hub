"""メッセージ対応ユースケース."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ec_hub.modules.messenger import Messenger

if TYPE_CHECKING:
    from ec_hub.context import AppContext

logger = logging.getLogger(__name__)


class MessageService:
    """バイヤーメッセージの処理を提供する."""

    def __init__(self, ctx: AppContext) -> None:
        self._ctx = ctx
        self._messenger = Messenger(ctx.db, ctx.settings)

    async def handle_message(
        self,
        buyer_username: str,
        body: str,
        ebay_message_id: str | None = None,
        order_id: int | None = None,
        listing_id: int | None = None,
        candidate_id: int | None = None,
    ) -> bool:
        """メッセージを分類し自動返信する."""
        return await self._messenger.handle_message(
            buyer_username=buyer_username,
            body=body,
            ebay_message_id=ebay_message_id,
            order_id=order_id,
            listing_id=listing_id,
            candidate_id=candidate_id,
        )

    async def check_and_process_messages(self) -> int:
        """新規メッセージを確認して処理する."""
        return await self._messenger.run()
