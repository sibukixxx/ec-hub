"""Amazon Product Advertising API (PA-API 5.0) クライアント.

仕様書 §4.1 に基づき、Amazon PA-APIを使用して仕入れ価格を取得する。
スクレイピングはAmazon規約違反のため、公式APIのみを使用する。

PA-API 5.0 の署名プロセス (AWS Signature V4) を実装。
https://webservices.amazon.co.jp/paapi5/documentation/
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

import httpx

from ec_hub.scrapers.base import SourceProduct, SourceSearcher, SourceSearchResult

logger = logging.getLogger(__name__)

# PA-API 5.0 エンドポイント
PAAPI_HOSTS = {
    "www.amazon.co.jp": "webservices.amazon.co.jp",
    "www.amazon.com": "webservices.amazon.com",
}
PAAPI_REGION = {
    "www.amazon.co.jp": "us-west-2",
    "www.amazon.com": "us-east-1",
}
SERVICE = "ProductAdvertisingAPI"


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _get_signature_key(secret_key: str, date_stamp: str, region: str, service: str) -> bytes:
    k_date = _sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    return _sign(k_service, "aws4_request")


class AmazonClient(SourceSearcher):
    """Amazon PA-API 5.0 クライアント."""

    def __init__(
        self,
        *,
        access_key: str,
        secret_key: str,
        partner_tag: str,
        country: str = "www.amazon.co.jp",
        timeout: float = 15.0,
    ) -> None:
        self._access_key = access_key
        self._secret_key = secret_key
        self._partner_tag = partner_tag
        self._country = country
        self._host = PAAPI_HOSTS.get(country, "webservices.amazon.co.jp")
        self._region = PAAPI_REGION.get(country, "us-west-2")
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def site_name(self) -> str:
        return "amazon"

    @property
    def is_configured(self) -> bool:
        return bool(self._access_key and self._secret_key and self._partner_tag)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _build_headers(self, operation: str, payload: str) -> dict[str, str]:
        """AWS Signature V4 で署名されたヘッダーを生成する."""
        now = datetime.now(timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        path = "/paapi5/" + operation.lower().replace(".", "/")

        # Canonical request
        content_type = "application/json; charset=utf-8"
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        canonical_headers = (
            f"content-encoding:amz-1.0\n"
            f"content-type:{content_type}\n"
            f"host:{self._host}\n"
            f"x-amz-date:{amz_date}\n"
            f"x-amz-target:com.amazon.paapi5.v1.ProductAdvertisingAPIv1.{operation}\n"
        )
        signed_headers = "content-encoding;content-type;host;x-amz-date;x-amz-target"

        canonical_request = (
            f"POST\n{path}\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
        )

        # String to sign
        credential_scope = f"{date_stamp}/{self._region}/{SERVICE}/aws4_request"
        string_to_sign = (
            f"AWS4-HMAC-SHA256\n{amz_date}\n{credential_scope}\n"
            + hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
        )

        # Signature
        signing_key = _get_signature_key(self._secret_key, date_stamp, self._region, SERVICE)
        signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

        authorization = (
            f"AWS4-HMAC-SHA256 Credential={self._access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

        return {
            "Authorization": authorization,
            "Content-Encoding": "amz-1.0",
            "Content-Type": content_type,
            "Host": self._host,
            "X-Amz-Date": amz_date,
            "X-Amz-Target": f"com.amazon.paapi5.v1.ProductAdvertisingAPIv1.{operation}",
        }

    async def _request(self, operation: str, payload: dict) -> dict:
        """PA-APIリクエストを送信する."""
        if not self.is_configured:
            raise RuntimeError("Amazon PA-API credentials not configured")

        payload_str = json.dumps(payload)
        headers = self._build_headers(operation, payload_str)
        url = f"https://{self._host}/paapi5/{operation.lower()}"

        client = await self._get_client()
        resp = await client.post(url, content=payload_str, headers=headers)
        resp.raise_for_status()
        return resp.json()

    async def search(self, query: str, *, max_results: int = 10) -> SourceSearchResult:
        """Amazon で商品を検索する."""
        if not self.is_configured:
            logger.warning("Amazon PA-API 未設定。空の結果を返します。")
            return SourceSearchResult(query=query, source_site=self.site_name)

        payload = {
            "Keywords": query,
            "Resources": [
                "ItemInfo.Title",
                "Offers.Listings.Price",
                "Images.Primary.Large",
                "ItemInfo.Classifications",
            ],
            "ItemCount": min(max_results, 10),
            "PartnerTag": self._partner_tag,
            "PartnerType": "Associates",
            "Marketplace": self._country,
        }

        try:
            data = await self._request("SearchItems", payload)
        except Exception as e:
            logger.error("Amazon PA-API SearchItems 失敗: %s", e)
            return SourceSearchResult(query=query, source_site=self.site_name)

        products = []
        for item in data.get("SearchResult", {}).get("Items", []):
            product = self._parse_item(item)
            if product:
                products.append(product)

        logger.info("Amazon検索 '%s': %d 件取得", query, len(products))
        return SourceSearchResult(query=query, source_site=self.site_name, products=products)

    async def get_item(self, item_code: str) -> SourceProduct | None:
        """ASIN から商品情報を取得する."""
        if not self.is_configured:
            logger.warning("Amazon PA-API 未設定。")
            return None

        payload = {
            "ItemIds": [item_code],
            "Resources": [
                "ItemInfo.Title",
                "Offers.Listings.Price",
                "Images.Primary.Large",
                "ItemInfo.Classifications",
            ],
            "PartnerTag": self._partner_tag,
            "PartnerType": "Associates",
            "Marketplace": self._country,
        }

        try:
            data = await self._request("GetItems", payload)
        except Exception as e:
            logger.error("Amazon PA-API GetItems 失敗: %s", e)
            return None

        items = data.get("ItemsResult", {}).get("Items", [])
        if not items:
            return None

        return self._parse_item(items[0])

    @staticmethod
    def _parse_item(item: dict) -> SourceProduct | None:
        """PA-APIレスポンスのアイテムをパースする."""
        asin = item.get("ASIN")
        if not asin:
            return None

        title_info = item.get("ItemInfo", {}).get("Title", {})
        title = title_info.get("DisplayValue", "")
        if not title:
            return None

        # 価格取得
        price_jpy = 0
        offers = item.get("Offers", {}).get("Listings", [])
        if offers:
            price_info = offers[0].get("Price", {})
            amount = price_info.get("Amount")
            if amount is not None:
                price_jpy = int(float(amount))

        if price_jpy <= 0:
            return None

        # 画像
        image_url = None
        images = item.get("Images", {}).get("Primary", {}).get("Large", {})
        if images:
            image_url = images.get("URL")

        # カテゴリ
        category = None
        classifications = item.get("ItemInfo", {}).get("Classifications", {})
        binding = classifications.get("Binding", {})
        if binding:
            category = binding.get("DisplayValue")

        url = item.get("DetailPageURL", f"https://www.amazon.co.jp/dp/{asin}")

        return SourceProduct(
            item_code=asin,
            source_site="amazon",
            title=title,
            price_jpy=price_jpy,
            url=url,
            image_url=image_url,
            category=category,
        )
