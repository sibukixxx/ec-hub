"""出品モジュール.

仕様書 §4.2 に基づく自動出品。
承認済み候補をeBay Inventory APIで出品する。
商品タイトルはDeepL/naniで英語翻訳し、テンプレートベースで商品説明を自動生成する。
セリングリミットを自動管理し、上限に達した場合はキューイングする。
"""

from __future__ import annotations

import logging

from ec_hub.config import load_fee_rules, load_settings
from ec_hub.db import Database
from ec_hub.modules.notifier import Notifier
from ec_hub.modules.profit_tracker import ProfitTracker
from ec_hub.services.ebay_api import EbayApiClient
from ec_hub.services.translator import Translator, create_translator

logger = logging.getLogger(__name__)

# eBay商品説明テンプレート
LISTING_DESCRIPTION_TEMPLATE = """
<div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto;">
  <h2>{title_en}</h2>
  <p><strong>Authentic item from Japan.</strong></p>
  <p>{description}</p>
  <hr/>
  <h3>Details</h3>
  <ul>
    <li><strong>Condition:</strong> {condition}</li>
    <li><strong>Ships from:</strong> Japan</li>
    <li><strong>Estimated delivery:</strong> 7-14 business days (International)</li>
  </ul>
  <hr/>
  <p style="font-size: 0.9em; color: #666;">
    Thank you for shopping with us! We ship worldwide from Japan.
    All items are carefully packaged to ensure safe delivery.
    Please feel free to contact us if you have any questions.
  </p>
</div>
""".strip()


class Lister:
    """eBay自動出品管理."""

    def __init__(
        self,
        db: Database,
        settings: dict | None = None,
        fee_rules: dict | None = None,
    ) -> None:
        self._db = db
        self._settings = settings or load_settings()
        self._fee_rules = fee_rules or load_fee_rules()
        self._listing_config = self._settings.get("listing", {})
        self._notifier = Notifier(self._settings)
        self._profit_tracker = ProfitTracker(db, self._settings, self._fee_rules)
        self._translator: Translator | None = None
        self._ebay_api: EbayApiClient | None = None

    @property
    def max_daily_listings(self) -> int:
        return self._listing_config.get("max_daily_listings", 10)

    @property
    def limit_warning_threshold(self) -> int:
        return self._listing_config.get("limit_warning_threshold", 3)

    def _get_translator(self) -> Translator:
        if self._translator is None:
            self._translator = create_translator(self._settings)
        return self._translator

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

    async def _prepare_listing_record(
        self,
        *,
        candidate_id: int,
        sku: str,
        title_en: str,
        description_html: str,
        listing_price: float,
        fx_rate: float,
    ) -> int | None:
        existing = await self._db.get_listing_by_sku(sku)
        if existing and existing.get("status") in {"active", "sold"}:
            logger.warning("既存の出品レコードが存在します: sku=%s, status=%s", sku, existing.get("status"))
            return None
        return await self._db.upsert_listing(
            candidate_id=candidate_id,
            sku=sku,
            title_en=title_en,
            description_html=description_html,
            listed_price_usd=listing_price,
            listed_fx_rate=fx_rate,
            status="draft",
        )

    async def translate_title(self, title_jp: str) -> str:
        """日本語タイトルを英語に翻訳する."""
        translator = self._get_translator()
        return await translator.translate(title_jp, source_lang="JA", target_lang="EN")

    def generate_listing_description(
        self,
        *,
        title_en: str,
        title_jp: str,
        condition: str = "New",
    ) -> str:
        """出品用の商品説明HTMLを生成する."""
        description = f"Original Japanese title: {title_jp}"
        return LISTING_DESCRIPTION_TEMPLATE.format(
            title_en=title_en,
            description=description,
            condition=condition,
        )

    def calc_listing_price(self, cost_jpy: int, weight_g: int, fx_rate: float) -> float:
        """利益率30%を確保する出品価格（USD）を逆算する.

        net_profit = jpy_revenue - total_cost
        margin_rate = net_profit / cost_jpy >= 0.30
        → jpy_revenue * (1 - fees_rate) >= cost_jpy * 1.30 + shipping + packing
        """
        fee_rules = self._fee_rules
        ebay_rate = fee_rules.get("ebay_fees", {}).get("default_rate", 0.1325)
        payoneer_rate = fee_rules.get("payoneer", {}).get("rate", 0.02)
        fx_buffer_rate = fee_rules.get("fx_buffer", {}).get("rate", 0.03)
        packing_cost = fee_rules.get("packing", {}).get("default_cost", 200)

        shipping_cost = self._profit_tracker.calc_shipping(weight_g, "US")

        net_rate = 1 - ebay_rate - payoneer_rate - fx_buffer_rate  # 0.8175
        target_revenue = (cost_jpy * 1.30 + shipping_cost + packing_cost) / net_rate
        price_usd = target_revenue / fx_rate

        # 切り上げて見栄え良く
        price_usd = round(price_usd + 0.5, 2)
        return max(price_usd, 0.99)

    async def list_candidate(self, candidate_id: int) -> bool:
        """承認済み候補をeBayに出品する.

        1. 商品タイトルを英語翻訳
        2. 出品説明を生成
        3. 利益率30%確保の価格を計算
        4. eBay Inventory APIで在庫アイテム作成 → オファー作成 → 公開
        """
        target = await self._db.get_candidate_by_id(candidate_id)
        if not target or target.get("status") != "approved":
            logger.warning("承認済み候補が見つかりません: id=%d", candidate_id)
            return False

        title_jp = target.get("title_jp", "")
        cost_jpy = target.get("cost_jpy", 0)
        weight_g = target.get("weight_g") or 500

        # 1. タイトル翻訳
        title_en = await self.translate_title(title_jp)
        logger.info("翻訳: %s → %s", title_jp[:30], title_en[:30])

        # 2. 商品説明生成
        description_html = self.generate_listing_description(
            title_en=title_en,
            title_jp=title_jp,
        )

        # 3. 出品価格計算
        fx_rate = await self._profit_tracker.get_fx_rate()
        listing_price = self.calc_listing_price(cost_jpy, weight_g, fx_rate)
        logger.info("出品価格: $%.2f (仕入¥%d, 為替%.2f)", listing_price, cost_jpy, fx_rate)

        # 4. eBay API出品
        ebay_api = self._get_ebay_api()
        sku = f"ECHUB-{candidate_id}"
        listing_row_id = await self._prepare_listing_record(
            candidate_id=candidate_id,
            sku=sku,
            title_en=title_en,
            description_html=description_html,
            listing_price=listing_price,
            fx_rate=fx_rate,
        )
        if listing_row_id is None:
            return False

        if not ebay_api.is_configured:
            logger.warning("eBay API未設定。出品をシミュレーションのみ実行。")
            await self._db.update_listing(listing_row_id, status="active")
            await self._db.update_candidate_status(candidate_id, "listed")
            return True

        try:
            await ebay_api.create_or_replace_inventory_item(
                sku,
                title=title_en,
                description=description_html,
                price_usd=listing_price,
                image_urls=[target.get("image_url")] if target.get("image_url") else [],
                weight_kg=weight_g / 1000,
            )
            await self._db.update_listing(listing_row_id, status="publishing")

            offer_data = await ebay_api.create_offer(
                sku,
                price_usd=listing_price,
                category_id=target.get("category", ""),
                listing_description=description_html,
            )
            offer_id = offer_data.get("offerId", "")
            listing_id = None

            if offer_id:
                publish_data = await ebay_api.publish_offer(offer_id)
                listing_id = publish_data.get("listingId")

            await self._db.update_listing(
                listing_row_id,
                offer_id=offer_id,
                listing_id=listing_id,
                status="active",
            )
            await self._db.update_candidate_status(candidate_id, "listed")
            logger.info("出品完了: %s ($%.2f)", title_en[:30], listing_price)
            return True

        except Exception as e:
            await self._db.update_listing(listing_row_id, status="failed")
            logger.error("eBay出品失敗: %s - %s", title_jp[:30], e)
            return False

    async def check_selling_limit(self) -> dict:
        """セリングリミットの残りを確認する."""
        current = await self._db.count_listings_by_status("active")
        ebay_api = self._get_ebay_api()
        if not ebay_api.is_configured:
            max_limit = 100
            return {"current": current, "max": max_limit, "remaining": max(0, max_limit - current)}

        try:
            limit_data = await ebay_api.get_selling_limit()
            quantity_limit = limit_data.get("quantity_limit", 100) or 100

            remaining = max(0, quantity_limit - current)

            if remaining <= self.limit_warning_threshold:
                await self._notifier.notify_selling_limit(remaining, quantity_limit)

            return {"current": current, "max": quantity_limit, "remaining": remaining}

        except Exception as e:
            logger.error("セリングリミット取得失敗: %s", e)
            return {"current": 0, "max": 100, "remaining": 100}

    async def run(self) -> int:
        """承認済み候補を自動出品する."""
        limit_info = await self.check_selling_limit()
        max_listings = min(self.max_daily_listings, limit_info["remaining"])

        if max_listings <= 0:
            logger.warning("セリングリミットに到達。出品をスキップします。")
            return 0

        approved = await self._db.get_candidates(status="approved")
        listed_count = 0

        for candidate in approved[:max_listings]:
            success = await self.list_candidate(candidate["id"])
            if success:
                listed_count += 1

        logger.info("出品完了: %d 件", listed_count)
        return listed_count

    async def close(self) -> None:
        if self._translator:
            await self._translator.close()
        if self._ebay_api:
            await self._ebay_api.close()
