"""バイヤー自動応答モジュール.

仕様書 §4.4 に基づくメッセージ自動応答。
Claude Haiku でバイヤーメッセージを高精度に分類し、
定型質問はテンプレートで即時返信、判定困難な場合はLINE通知して人手に回す。

分類フロー:
1. Claude Haiku API で分類を試行 (高精度)
2. API未設定 or エラー時はキーワードマッチングにフォールバック
"""

from __future__ import annotations

import logging
import re

import anthropic

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

# キーワードベースの分類パターン (フォールバック用)
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

# Claude Haiku 分類プロンプト
CLASSIFICATION_SYSTEM_PROMPT = """You are a message classifier for an eBay seller who ships items from Japan.
Classify the buyer's message into exactly one of the following categories:

- shipping_tracking: Questions about shipping status, tracking numbers, delivery time, when item will ship
- condition: Questions about item condition, authenticity, quality, defects
- return_cancel: Requests to return, cancel, or refund an order, complaints about wrong/damaged items
- address_change: Requests to change or update shipping address
- other: Messages that don't fit any of the above categories

Respond with ONLY the category name, nothing else."""


class _ClaudeClassifier:
    """Claude Haiku を使ったメッセージ分類."""

    # 有効なカテゴリ名のマッピング
    CATEGORY_MAP: dict[str, MessageCategory] = {
        "shipping_tracking": MessageCategory.SHIPPING_TRACKING,
        "condition": MessageCategory.CONDITION,
        "return_cancel": MessageCategory.RETURN_CANCEL,
        "address_change": MessageCategory.ADDRESS_CHANGE,
        "other": MessageCategory.OTHER,
    }

    def __init__(self, api_key: str, *, model: str = "claude-haiku-4-5-20251001") -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def classify(self, body: str) -> MessageCategory:
        """Claude Haiku でメッセージを分類する."""
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=32,
            system=CLASSIFICATION_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": body},
            ],
        )
        result_text = response.content[0].text.strip().lower()

        category = self.CATEGORY_MAP.get(result_text)
        if category is None:
            logger.warning("Claude Haiku が未知のカテゴリを返しました: '%s'", result_text)
            return MessageCategory.OTHER
        return category


class Messenger:
    """バイヤーメッセージの自動分類・応答."""

    def __init__(self, db: Database, settings: dict | None = None) -> None:
        self._db = db
        self._settings = settings or load_settings()
        self._notifier = Notifier(self._settings)
        self._claude_classifier: _ClaudeClassifier | None = None
        self._init_claude_classifier()

    def _init_claude_classifier(self) -> None:
        """Claude Haiku 分類器を初期化する."""
        claude_config = self._settings.get("claude", {})
        api_key = claude_config.get("api_key", "")
        if api_key:
            model = claude_config.get("model", "claude-haiku-4-5-20251001")
            self._claude_classifier = _ClaudeClassifier(api_key, model=model)
            logger.info("Claude Haiku 分類器を有効化 (model=%s)", model)

    @property
    def has_claude_classifier(self) -> bool:
        """Claude Haiku 分類器が利用可能か."""
        return self._claude_classifier is not None

    async def classify_message(self, body: str) -> MessageCategory:
        """メッセージをカテゴリに分類する.

        1. Claude Haiku API が設定済みなら高精度分類を試行
        2. 失敗時またはAPI未設定時はキーワードマッチングにフォールバック
        """
        if self._claude_classifier:
            try:
                category = await self._claude_classifier.classify(body)
                logger.debug("Claude分類: '%s' → %s", body[:40], category.value)
                return category
            except Exception as e:
                logger.warning("Claude分類失敗、フォールバックに切替: %s", e)

        return self.classify_by_keywords(body)

    def classify_by_keywords(self, body: str) -> MessageCategory:
        """キーワードマッチングによるフォールバック分類."""
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
        listing_id: int | None = None,
        candidate_id: int | None = None,
    ) -> bool:
        """メッセージを処理する.

        Returns:
            True: 自動応答した, False: エスカレーションした
        """
        # Resolve listing_id from order if not provided
        if listing_id is None and order_id is not None:
            order = await self._db.get_order_by_id(order_id)
            if order:
                listing_id = order.get("listing_id")

        category = await self.classify_message(body)

        await self._db.add_message(
            buyer_username=buyer_username,
            body=body,
            ebay_message_id=ebay_message_id,
            order_id=order_id,
            listing_id=listing_id,
            candidate_id=candidate_id,
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
                listing_id=listing_id,
                candidate_id=candidate_id,
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
