"""バイヤー自動応答モジュール.

仕様書 §4.4 に基づくメッセージ自動応答。
定型質問はテンプレートで即時返信し、判定困難な場合はLINE通知して人手に回す。
"""

from __future__ import annotations

import logging
import re

from ec_hub.config import load_settings
from ec_hub.db import Database
from ec_hub.models import MessageCategory
from ec_hub.modules.notifier import Notifier

logger = logging.getLogger(__name__)

# テンプレート応答
TEMPLATES: dict[MessageCategory, str] = {
    MessageCategory.SHIPPING_TRACKING: (
        "Thank you for your message! Your item will be shipped within 2-3 business days "
        "after purchase confirmation. Once shipped, I will update the tracking information. "
        "International shipping from Japan typically takes 7-14 business days. "
        "Thank you for your patience!"
    ),
    MessageCategory.CONDITION: (
        "Thank you for your inquiry! This item is authentic and sourced directly from Japan. "
        "Please refer to the item condition listed in the description. "
        "If you have any specific questions about the condition, please let me know!"
    ),
    MessageCategory.RETURN_CANCEL: (
        "Thank you for reaching out. Our return policy follows eBay's standard return policy. "
        "If you'd like to request a return or cancellation, please initiate the process through eBay. "
        "We'll do our best to assist you promptly."
    ),
    MessageCategory.ADDRESS_CHANGE: (
        "Thank you for your message. Unfortunately, we cannot change the shipping address "
        "after the order has been placed due to eBay's policy. "
        "Please contact eBay customer support if you need to update your address. "
        "If the item hasn't shipped yet, we may be able to help - please let us know ASAP."
    ),
}

# キーワードベースの分類パターン
CATEGORY_PATTERNS: dict[MessageCategory, list[str]] = {
    MessageCategory.SHIPPING_TRACKING: [
        r"when.*ship", r"tracking", r"shipped\?", r"delivery",
        r"how long", r"arrive", r"dispatch",
    ],
    MessageCategory.CONDITION: [
        r"condition", r"\bnew\b", r"\bused\b", r"authentic",
        r"original", r"quality", r"defect",
    ],
    MessageCategory.RETURN_CANCEL: [
        r"cancel", r"return", r"refund", r"money back",
        r"wrong item", r"damaged", r"broken",
    ],
    MessageCategory.ADDRESS_CHANGE: [
        r"change.*address", r"update.*address", r"wrong address",
        r"new address", r"different address",
    ],
}


class Messenger:
    """バイヤーメッセージの自動分類・応答."""

    def __init__(self, db: Database, settings: dict | None = None) -> None:
        self._db = db
        self._settings = settings or load_settings()
        self._notifier = Notifier(self._settings)

    def classify_message(self, body: str) -> MessageCategory:
        """メッセージをカテゴリに分類する.

        キーワードマッチングによる分類。
        TODO: Claude API (Haiku) による高精度分類に置き換え
        """
        text = body.lower()
        for category, patterns in CATEGORY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    return category
        return MessageCategory.OTHER

    def get_template_reply(self, category: MessageCategory) -> str | None:
        """カテゴリに対応するテンプレート応答を取得する."""
        return TEMPLATES.get(category)

    async def handle_message(
        self,
        *,
        buyer_username: str,
        body: str,
        ebay_message_id: str | None = None,
        order_id: int | None = None,
    ) -> bool:
        """メッセージを処理する.

        Returns:
            True: 自動応答した, False: エスカレーションした
        """
        category = self.classify_message(body)

        await self._db.add_message(
            buyer_username=buyer_username,
            body=body,
            ebay_message_id=ebay_message_id,
            order_id=order_id,
            category=category.value,
        )

        if category == MessageCategory.OTHER:
            await self._notifier.notify_message_escalation(buyer_username, body)
            logger.info("メッセージをエスカレーション: %s", buyer_username)
            return False

        reply = self.get_template_reply(category)
        if reply:
            # TODO: eBay API経由で返信を送信
            await self._db.add_message(
                buyer_username=buyer_username,
                body=reply,
                direction="outbound",
                order_id=order_id,
                category=category.value,
                auto_replied=True,
            )
            logger.info("自動応答: %s → %s", buyer_username, category.value)
            return True

        return False

    async def check_new_messages(self) -> list[dict]:
        """eBay APIで新着メッセージを確認する.

        TODO: eBay API (Trading API - GetMyMessages) で未読メッセージを取得
        """
        return []

    async def run(self) -> int:
        """新着メッセージを確認して処理する.

        Returns:
            処理したメッセージ数
        """
        messages = await self.check_new_messages()
        processed = 0
        for msg in messages:
            await self.handle_message(**msg)
            processed += 1
        return processed
