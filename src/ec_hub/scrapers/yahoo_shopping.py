"""Yahoo!ショッピング 商品検索 API クライアント.

Yahoo!ショッピング 商品検索 (v3) API を使用して仕入れ価格を取得する。
https://developer.yahoo.co.jp/webapi/shopping/v3/itemsearch.html

Rate Limit: 1リクエスト/秒
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from ec_hub.scrapers.base import SourceProduct, SourceSearcher, SourceSearchResult

logger = logging.getLogger(__name__)

YAHOO_SEARCH_URL = "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch"
YAHOO_RATE_LIMIT_INTERVAL = 1.1  # 1秒 + マージン


class YahooShoppingClient(SourceSearcher):
    """Yahoo!ショッピング 商品検索APIクライアント."""

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
        return "yahoo_shopping"

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
        if elapsed < YAHOO_RATE_LIMIT_INTERVAL:
            await asyncio.sleep(YAHOO_RATE_LIMIT_INTERVAL - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()

    async def _request(self, params: dict) -> dict:
        """Yahoo!ショッピングAPIリクエストを送信する."""
        if not self.is_configured:
            raise RuntimeError("Yahoo Shopping API app_id not configured")

        await self._rate_limit()
        params["appid"] = self._app_id

        client = await self._get_client()
        resp = await client.get(YAHOO_SEARCH_URL, params=params)
        resp.raise_for_status()
        return resp.json()

    async def search(self, query: str, *, max_results: int = 10) -> SourceSearchResult:
        """Yahoo!ショッピングで商品を検索する."""
        if not self.is_configured:
            logger.warning("Yahoo!ショッピングAPI 未設定。空の結果を返します。")
            return SourceSearchResult(query=query, source_site=self.site_name)

        params = {
            "query": query,
            "results": min(max_results, 50),
            "sort": "-score",
            "in_stock": "true",
        }

        try:
            data = await self._request(params)
        except Exception as e:
            logger.error("Yahoo!ショッピングAPI検索失敗: %s", e)
            return SourceSearchResult(query=query, source_site=self.site_name)

        products = []
        for item in data.get("hits", []):
            product = self._parse_item(item)
            if product:
                products.append(product)

        logger.info("Yahoo!ショッピング検索 '%s': %d 件取得", query, len(products))
        return SourceSearchResult(query=query, source_site=self.site_name, products=products)

    async def get_item(self, item_code: str) -> SourceProduct | None:
        """商品コードから商品情報を取得する."""
        if not self.is_configured:
            logger.warning("Yahoo!ショッピングAPI 未設定。")
            return None

        params = {
            "query": item_code,
            "results": 1,
        }

        try:
            data = await self._request(params)
        except Exception as e:
            logger.error("Yahoo!ショッピングAPI商品取得失敗: %s", e)
            return None

        hits = data.get("hits", [])
        if not hits:
            return None

        return self._parse_item(hits[0])

    @staticmethod
    def _parse_item(item: dict) -> SourceProduct | None:
        """Yahoo!ショッピングAPIレスポンスのアイテムをパースする."""
        name = item.get("name", "")
        if not name:
            return None

        price = item.get("price")
        if not price or int(price) <= 0:
            return None

        item_code = item.get("code", "")
        url = item.get("url", "")

        # 画像URL
        image_url = None
        image_data = item.get("image", {})
        if isinstance(image_data, dict):
            image_url = image_data.get("medium") or image_data.get("small")

        # カテゴリ
        category = None
        genre = item.get("genreCategory")
        if isinstance(genre, dict):
            category = genre.get("name")

        # レビュー
        review_count = None
        rating = None
        review_data = item.get("review", {})
        if isinstance(review_data, dict):
            review_count = review_data.get("count")
            raw_rate = review_data.get("rate")
            if raw_rate:
                try:
                    rating = float(raw_rate)
                except (ValueError, TypeError):
                    rating = None

        # 在庫
        availability = item.get("inStock", True)

        return SourceProduct(
            item_code=item_code,
            source_site="yahoo_shopping",
            title=name,
            price_jpy=int(price),
            url=url,
            image_url=image_url,
            category=category,
            review_count=review_count,
            rating=rating,
            availability=bool(availability),
        )
