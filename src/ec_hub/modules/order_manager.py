"""受注・仕入れ管理モジュール.

仕様書 §4.3 に基づく注文管理。
eBay Fulfillment APIで注文を検知し、仕入れ・発送フローを管理する。
仕入れ・発送は人手対応とし、追跡番号登録とフィードバック依頼を自動化する。

注文ステータスフロー:
  awaiting_purchase → purchased → shipped → delivered → completed
"""

from __future__ import annotations

import logging

from ec_hub.config import load_fee_rules, load_settings
from ec_hub.db import Database
from ec_hub.modules.notifier import Notifier
from ec_hub.modules.profit_tracker import ProfitTracker
from ec_hub.services.ebay_api import EbayApiClient

logger = logging.getLogger(__name__)


class OrderManager:
    """eBay注文の検知・管理."""

    def __init__(
        self,
        db: Database,
        settings: dict | None = None,
        fee_rules: dict | None = None,
    ) -> None:
        self._db = db
        self._settings = settings or load_settings()
        self._fee_rules = fee_rules or load_fee_rules()
        self._notifier = Notifier(self._settings)
        self._profit_tracker = ProfitTracker(db, self._settings, self._fee_rules)
        self._ebay_api: EbayApiClient | None = None

    def _get_ebay_api(self) -> EbayApiClient:
        if self._ebay_api is None:
            ebay_config = self._settings.get("ebay", {})
            self._ebay_api = EbayApiClient(
                app_id=ebay_config.get("app_id", ""),
                cert_id=ebay_config.get("cert_id", ""),
                dev_id=ebay_config.get("dev_id", ""),
                user_token=ebay_config.get("user_token", ""),
                sandbox=ebay_config.get("sandbox", True),
            )
        return self._ebay_api

    async def check_new_orders(self) -> list[dict]:
        """eBay Fulfillment APIで新規注文を確認する."""
        ebay_api = self._get_ebay_api()
        if not ebay_api.is_configured:
            logger.warning("eBay API未設定。注文確認をスキップします。")
            return []

        try:
            data = await ebay_api.get_orders(
                limit=50,
                order_fulfillment_status="NOT_STARTED",
            )
        except Exception as e:
            logger.error("eBay注文取得失敗: %s", e)
            return []

        new_orders = []
        existing_orders = await self._db.get_orders(limit=1000)
        existing_ids = {o["ebay_order_id"] for o in existing_orders}

        for order in data.get("orders", []):
            order_id = order.get("orderId", "")
            if not order_id or order_id in existing_ids:
                continue

            buyer = order.get("buyer", {}).get("username", "")
            price_summary = order.get("pricingSummary", {})
            total = price_summary.get("total", {})
            sale_price = float(total.get("value", 0))

            ship_to = order.get("fulfillmentStartInstructions", [{}])[0]
            shipping_step = ship_to.get("shippingStep", {})
            ship_to_address = shipping_step.get("shipTo", {}).get("contactAddress", {})
            country = ship_to_address.get("countryCode", "US")

            new_orders.append({
                "ebay_order_id": order_id,
                "buyer_username": buyer,
                "sale_price_usd": sale_price,
                "destination_country": country,
            })

        return new_orders

    async def register_order(
        self,
        *,
        ebay_order_id: str,
        buyer_username: str,
        sale_price_usd: float,
        destination_country: str,
        candidate_id: int | None = None,
        listing_id: int | None = None,
    ) -> int:
        """新規注文をDBに登録しLINE通知する."""
        order_id = await self._db.add_order(
            ebay_order_id=ebay_order_id,
            candidate_id=candidate_id,
            listing_id=listing_id,
            buyer_username=buyer_username,
            sale_price_usd=sale_price_usd,
            destination_country=destination_country,
        )
        await self._notifier.notify_order(ebay_order_id, sale_price_usd)
        logger.info("注文登録: %s ($%.2f) → %s", ebay_order_id, sale_price_usd, destination_country)
        return order_id

    async def mark_purchased(self, order_id: int, actual_cost_jpy: int) -> None:
        """仕入れ完了を記録する."""
        await self._db.update_order(order_id, status="purchased", actual_cost_jpy=actual_cost_jpy)
        logger.info("仕入れ完了: order_id=%d, cost=¥%d", order_id, actual_cost_jpy)

    async def mark_shipped(
        self,
        order_id: int,
        tracking_number: str,
        shipping_cost_jpy: int,
        *,
        shipping_carrier: str = "JP_POST",
    ) -> None:
        """発送完了を記録し、追跡番号をeBayに自動登録する."""
        await self._db.update_order(
            order_id,
            status="shipped",
            tracking_number=tracking_number,
            actual_shipping_jpy=shipping_cost_jpy,
        )

        # eBay Fulfillment API で追跡番号を登録
        target = await self._db.get_order_by_id(order_id)
        if target:
            ebay_api = self._get_ebay_api()
            if ebay_api.is_configured:
                try:
                    await ebay_api.create_shipping_fulfillment(
                        target["ebay_order_id"],
                        tracking_number=tracking_number,
                        shipping_carrier=shipping_carrier,
                    )
                    logger.info(
                        "eBayに追跡番号登録: order=%s, tracking=%s",
                        target["ebay_order_id"], tracking_number,
                    )
                except Exception as e:
                    logger.error("eBay追跡番号登録失敗: %s", e)

        logger.info("発送完了: order_id=%d, tracking=%s", order_id, tracking_number)

    async def mark_delivered(self, order_id: int) -> None:
        """配達完了を記録する."""
        await self._db.update_order(order_id, status="delivered")
        logger.info("配達完了: order_id=%d", order_id)

    async def complete_order(self, order_id: int) -> None:
        """注文を完了し、利益を確定させる.

        実際の仕入れ価格・送料から純利益を再計算してDBに記録する。
        """
        target = await self._db.get_order_by_id(order_id)
        if not target:
            logger.error("注文が見つかりません: order_id=%d", order_id)
            return

        sale_price_usd = target.get("sale_price_usd", 0)
        actual_cost = target.get("actual_cost_jpy", 0) or 0
        actual_shipping = target.get("actual_shipping_jpy", 0) or 0
        packing = target.get("packing_cost_jpy", 200)
        destination = target.get("destination_country", "US")

        fx_rate = await self._profit_tracker.get_fx_rate()
        breakdown = self._profit_tracker.calc_net_profit(
            jpy_cost=actual_cost,
            ebay_price_usd=sale_price_usd,
            weight_g=500,
            destination=destination,
            fx_rate=fx_rate,
        )

        # 実際の送料で再計算
        actual_net_profit = breakdown.jpy_revenue - (
            actual_cost + breakdown.ebay_fee + breakdown.payoneer_fee
            + actual_shipping + packing + breakdown.fx_buffer
        )

        await self._db.update_order(
            order_id,
            status="completed",
            net_profit_jpy=actual_net_profit,
            fx_rate=fx_rate,
            ebay_fee_jpy=breakdown.ebay_fee,
            payoneer_fee_jpy=breakdown.payoneer_fee,
        )
        logger.info("注文完了: order_id=%d, 確定利益=¥%d", order_id, actual_net_profit)

    async def run(self) -> int:
        """新規注文を確認して処理する."""
        new_orders = await self.check_new_orders()
        for order_data in new_orders:
            await self.register_order(**order_data)
        logger.info("注文確認完了: %d 件の新規注文", len(new_orders))
        return len(new_orders)

    async def close(self) -> None:
        if self._ebay_api:
            await self._ebay_api.close()
