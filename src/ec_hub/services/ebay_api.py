"""eBay REST API クライアント.

eBay の各REST APIを統合するクライアント:
- Trading API: 出品管理・セリングリミット確認
- Fulfillment API: 注文管理・発送情報登録
- Browse API: 商品情報取得

https://developer.ebay.com/docs
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

EBAY_API_SANDBOX = "https://api.sandbox.ebay.com"
EBAY_API_PRODUCTION = "https://api.ebay.com"


class EbayApiClient:
    """eBay REST API クライアント."""

    def __init__(
        self,
        *,
        app_id: str,
        cert_id: str,
        dev_id: str,
        user_token: str,
        sandbox: bool = True,
        timeout: float = 30.0,
    ) -> None:
        self._app_id = app_id
        self._cert_id = cert_id
        self._dev_id = dev_id
        self._user_token = user_token
        self._base_url = EBAY_API_SANDBOX if sandbox else EBAY_API_PRODUCTION
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def is_configured(self) -> bool:
        return bool(self._app_id and self._user_token)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                headers={
                    "Authorization": f"Bearer {self._user_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> EbayApiClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    # --- Inventory API (出品管理) ---

    async def create_or_replace_inventory_item(
        self,
        sku: str,
        *,
        title: str,
        description: str,
        price_usd: float,
        quantity: int = 1,
        condition: str = "NEW",
        image_urls: list[str] | None = None,
        category_id: str | None = None,
        weight_kg: float | None = None,
    ) -> dict:
        """Inventory API で在庫アイテムを作成/更新する.

        https://developer.ebay.com/api-docs/sell/inventory/resources/inventory_item/methods/createOrReplaceInventoryItem
        """
        if not self.is_configured:
            raise RuntimeError("eBay API credentials not configured")

        payload: dict = {
            "product": {
                "title": title,
                "description": description,
                "imageUrls": image_urls or [],
            },
            "condition": condition,
            "availability": {
                "shipToLocationAvailability": {
                    "quantity": quantity,
                },
            },
        }

        if weight_kg:
            payload["packageWeightAndSize"] = {
                "weight": {
                    "value": weight_kg,
                    "unit": "KILOGRAM",
                },
            }

        client = await self._get_client()
        resp = await client.put(
            f"/sell/inventory/v1/inventory_item/{sku}",
            json=payload,
        )
        resp.raise_for_status()
        logger.info("Inventory item created/updated: SKU=%s", sku)
        return {"sku": sku, "status": resp.status_code}

    async def create_offer(
        self,
        sku: str,
        *,
        marketplace_id: str = "EBAY_US",
        price_usd: float,
        currency: str = "USD",
        category_id: str,
        listing_description: str,
        fulfillment_policy_id: str | None = None,
        payment_policy_id: str | None = None,
        return_policy_id: str | None = None,
    ) -> dict:
        """Inventory API で出品オファーを作成する.

        https://developer.ebay.com/api-docs/sell/inventory/resources/offer/methods/createOffer
        """
        if not self.is_configured:
            raise RuntimeError("eBay API credentials not configured")

        payload: dict = {
            "sku": sku,
            "marketplaceId": marketplace_id,
            "format": "FIXED_PRICE",
            "listingDescription": listing_description,
            "pricingSummary": {
                "price": {
                    "value": str(price_usd),
                    "currency": currency,
                },
            },
            "categoryId": category_id,
            "merchantLocationKey": "default",
        }

        if fulfillment_policy_id:
            payload["listingPolicies"] = payload.get("listingPolicies", {})
            payload["listingPolicies"]["fulfillmentPolicyId"] = fulfillment_policy_id
        if payment_policy_id:
            payload["listingPolicies"] = payload.get("listingPolicies", {})
            payload["listingPolicies"]["paymentPolicyId"] = payment_policy_id
        if return_policy_id:
            payload["listingPolicies"] = payload.get("listingPolicies", {})
            payload["listingPolicies"]["returnPolicyId"] = return_policy_id

        client = await self._get_client()
        resp = await client.post("/sell/inventory/v1/offer", json=payload)
        resp.raise_for_status()
        data = resp.json()
        offer_id = data.get("offerId", "")
        logger.info("Offer created: SKU=%s, offerId=%s", sku, offer_id)
        return data

    async def publish_offer(self, offer_id: str) -> dict:
        """オファーを公開（出品開始）する.

        https://developer.ebay.com/api-docs/sell/inventory/resources/offer/methods/publishOffer
        """
        if not self.is_configured:
            raise RuntimeError("eBay API credentials not configured")

        client = await self._get_client()
        resp = await client.post(f"/sell/inventory/v1/offer/{offer_id}/publish")
        resp.raise_for_status()
        data = resp.json()
        listing_id = data.get("listingId", "")
        logger.info("Offer published: offerId=%s, listingId=%s", offer_id, listing_id)
        return data

    # --- Fulfillment API (注文管理) ---

    async def get_orders(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        order_fulfillment_status: str | None = None,
    ) -> dict:
        """Fulfillment API で注文一覧を取得する.

        https://developer.ebay.com/api-docs/sell/fulfillment/resources/order/methods/getOrders
        """
        if not self.is_configured:
            raise RuntimeError("eBay API credentials not configured")

        params: dict[str, str] = {
            "limit": str(limit),
            "offset": str(offset),
        }
        if order_fulfillment_status:
            params["filter"] = f"orderfulfillmentstatus:{{{order_fulfillment_status}}}"

        client = await self._get_client()
        resp = await client.get("/sell/fulfillment/v1/order", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_order(self, order_id: str) -> dict:
        """Fulfillment API で注文詳細を取得する."""
        if not self.is_configured:
            raise RuntimeError("eBay API credentials not configured")

        client = await self._get_client()
        resp = await client.get(f"/sell/fulfillment/v1/order/{order_id}")
        resp.raise_for_status()
        return resp.json()

    async def create_shipping_fulfillment(
        self,
        order_id: str,
        *,
        tracking_number: str,
        shipping_carrier: str = "JP_POST",
        line_items: list[dict] | None = None,
    ) -> dict:
        """Fulfillment API で発送情報（追跡番号）を登録する.

        https://developer.ebay.com/api-docs/sell/fulfillment/resources/order/shipping_fulfillment/methods/createShippingFulfillment
        """
        if not self.is_configured:
            raise RuntimeError("eBay API credentials not configured")

        payload: dict = {
            "trackingNumber": tracking_number,
            "shippingCarrierCode": shipping_carrier,
            "shippedDate": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        }
        if line_items:
            payload["lineItems"] = line_items

        client = await self._get_client()
        resp = await client.post(
            f"/sell/fulfillment/v1/order/{order_id}/shipping_fulfillment",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        fulfillment_id = data.get("fulfillmentId", "")
        logger.info(
            "Shipping fulfillment created: order=%s, tracking=%s, fulfillment=%s",
            order_id, tracking_number, fulfillment_id,
        )
        return data

    # --- Account API (セリングリミット) ---

    async def get_selling_limit(self) -> dict:
        """現在のセリングリミットを取得する.

        https://developer.ebay.com/api-docs/sell/account/resources/privilege/methods/getPrivileges
        """
        if not self.is_configured:
            raise RuntimeError("eBay API credentials not configured")

        client = await self._get_client()
        resp = await client.get("/sell/account/v1/privilege")
        resp.raise_for_status()
        data = resp.json()

        selling_limit = data.get("sellingLimit", {})
        return {
            "amount_limit": selling_limit.get("amount", {}).get("value"),
            "quantity_limit": selling_limit.get("quantity"),
        }
