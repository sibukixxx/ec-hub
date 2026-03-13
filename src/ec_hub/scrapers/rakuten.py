"""楽天商品検索 API クライアント.

楽天 Ichiba Item Search API (v2) を使用して仕入れ価格を取得する。
https://webservice.rakuten.co.jp/documentation/ichiba-item-search

Rate Limit: 1リクエスト/秒
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from ec_hub.scrapers.base import SourceProduct, SourceSearcher, SourceSearchResult

logger = logging.getLogger(__name__)

RAKUTEN_SEARCH_URL = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"
RAKUTEN_RATE_LIMIT_INTERVAL = 1.1  # 1秒 + マージン


class RakutenClient(SourceSearcher):
    """楽天商品検索APIクライアント."""

    def __init__(
        self,
        *,
        app_id: str,
        timeout: float = 15.0,
    ) -> None:
        self._app_id = app_id
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._last_request_time: float = 0

    @property
    def site_name(self) -> str:
        return "rakuten"

    @property
    def is_configured(self) -> bool:
        return bool(self._app_id)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _rate_limit(self) -> None:
        """レートリミット (1リクエスト/秒) を遵守する."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < RAKUTEN_RATE_LIMIT_INTERVAL:
            await asyncio.sleep(RAKUTEN_RATE_LIMIT_INTERVAL - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()

    async def _request(self, params: dict) -> dict:
        """楽天APIリクエストを送信する."""
        if not self.is_configured:
            raise RuntimeError("Rakuten API app_id not configured")

        await self._rate_limit()
        params["applicationId"] = self._app_id
        params["format"] = "json"
        params["formatVersion"] = "2"

        client = await self._get_client()
        resp = await client.get(RAKUTEN_SEARCH_URL, params=params)
        resp.raise_for_status()
        return resp.json()

    async def search(self, query: str, *, max_results: int = 10) -> SourceSearchResult:
        """楽天で商品を検索する."""
        if not self.is_configured:
            logger.warning("楽天API 未設定。空の結果を返します。")
            return SourceSearchResult(query=query, source_site=self.site_name)

        params = {
            "keyword": query,
            "hits": min(max_results, 30),
            "sort": "standard",
            "availability": 1,  # 在庫ありのみ
        }

        try:
            data = await self._request(params)
        except Exception as e:
            logger.error("楽天API検索失敗: %s", e)
            return SourceSearchResult(query=query, source_site=self.site_name)

        products = []
        for item in data.get("Items", []):
            product = self._parse_item(item)
            if product:
                products.append(product)

        logger.info("楽天検索 '%s': %d 件取得", query, len(products))
        return SourceSearchResult(query=query, source_site=self.site_name, products=products)

    async def get_item(self, item_code: str) -> SourceProduct | None:
        """楽天商品コードから商品情報を取得する."""
        if not self.is_configured:
            logger.warning("楽天API 未設定。")
            return None

        params = {
            "itemCode": item_code,
        }

        try:
            data = await self._request(params)
        except Exception as e:
            logger.error("楽天API商品取得失敗: %s", e)
            return None

        items = data.get("Items", [])
        if not items:
            return None

        return self._parse_item(items[0])

    @staticmethod
    def _parse_item(item: dict) -> SourceProduct | None:
        """楽天APIレスポンスのアイテムをパースする."""
        title = item.get("itemName", "")
        if not title:
            return None

        price = item.get("itemPrice")
        if not price or int(price) <= 0:
            return None

        item_code = item.get("itemCode", "")
        url = item.get("itemUrl", "")

        # 画像URL（複数ある場合は最初の1枚）
        image_url = None
        images = item.get("mediumImageUrls", [])
        if images:
            if isinstance(images[0], dict):
                image_url = images[0].get("imageUrl")
            elif isinstance(images[0], str):
                image_url = images[0]

        # カテゴリ
        category = item.get("genreName")

        # レビュー
        review_count = item.get("reviewCount")
        rating = item.get("reviewAverage")
        if rating:
            try:
                rating = float(rating)
            except (ValueError, TypeError):
                rating = None

        # 在庫
        availability = item.get("availability", 1) == 1

        return SourceProduct(
            item_code=item_code,
            source_site="rakuten",
            title=title,
            price_jpy=int(price),
            url=url,
            image_url=image_url,
            category=category,
            review_count=review_count,
            rating=rating,
            availability=availability,
        )
