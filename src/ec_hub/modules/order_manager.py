"""受注・仕入れ管理モジュール.

仕様書 §4.3 に基づく注文管理。
eBayの注文を検知し、仕入れ・発送フローを管理する。
"""

from __future__ import annotations

import logging

from ec_hub.config import load_settings
from ec_hub.db import Database
from ec_hub.modules.notifier import Notifier

logger = logging.getLogger(__name__)


class OrderManager:
    """eBay注文の検知・管理."""

    def __init__(self, db: Database, settings: dict | None = None) -> None:
        self._db = db
        self._settings = settings or load_settings()
        self._notifier = Notifier(self._settings)

    async def check_new_orders(self) -> list[dict]:
        """eBay APIで新規注文を確認する.

        TODO: eBay API (Fulfillment API) で注文を取得
        """
        # プレースホルダ
        new_orders: list[dict] = []
        return new_orders

    async def register_order(
        self,
        *,
        ebay_order_id: str,
        buyer_username: str,
        sale_price_usd: float,
        destination_country: str,
        candidate_id: int | None = None,
    ) -> int:
        """新規注文をDBに登録しLINE通知する."""
        order_id = await self._db.add_order(
            ebay_order_id=ebay_order_id,
            candidate_id=candidate_id,
            buyer_username=buyer_username,
            sale_price_usd=sale_price_usd,
            destination_country=destination_country,
        )
        await self._notifier.notify_order(ebay_order_id, sale_price_usd)
        logger.info("注文登録: %s ($%.2f)", ebay_order_id, sale_price_usd)
        return order_id

    async def mark_purchased(self, order_id: int, actual_cost_jpy: int) -> None:
        """仕入れ完了を記録する."""
        await self._db.update_order(order_id, status="purchased", actual_cost_jpy=actual_cost_jpy)
        logger.info("仕入れ完了: order_id=%d, cost=¥%d", order_id, actual_cost_jpy)

    async def mark_shipped(self, order_id: int, tracking_number: str, shipping_cost_jpy: int) -> None:
        """発送完了を記録し、追跡番号をeBayに登録する.

        TODO: eBay APIで追跡番号を自動登録
        """
        await self._db.update_order(
            order_id,
            status="shipped",
            tracking_number=tracking_number,
            actual_shipping_jpy=shipping_cost_jpy,
        )
        logger.info("発送完了: order_id=%d, tracking=%s", order_id, tracking_number)

    async def mark_delivered(self, order_id: int) -> None:
        """配達完了を記録し、フィードバック依頼を送信する.

        TODO: eBay APIでフィードバック依頼メッセージを自動送信
        """
        await self._db.update_order(order_id, status="delivered")
        logger.info("配達完了: order_id=%d", order_id)

    async def complete_order(self, order_id: int, net_profit_jpy: int) -> None:
        """注文を完了し、利益を確定させる."""
        await self._db.update_order(order_id, status="completed", net_profit_jpy=net_profit_jpy)
        logger.info("注文完了: order_id=%d, 利益=¥%d", order_id, net_profit_jpy)

    async def run(self) -> int:
        """新規注文を確認して処理する.

        Returns:
            新規検知した注文数
        """
        new_orders = await self.check_new_orders()
        for order_data in new_orders:
            await self.register_order(**order_data)
        return len(new_orders)
