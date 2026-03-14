"""無印良品 商品スクレイパー.

無印良品ネットストアから商品情報をスクレイピングする。
公式APIが存在しないため httpx + BeautifulSoup でHTML解析。

Rate Limit: 2リクエスト/秒 (polite scraping)
"""

from __future__ import annotations

import asyncio
import logging
import re

import httpx
from bs4 import BeautifulSoup, Tag

from ec_hub.scrapers.base import SourceProduct, SourceSearcher, SourceSearchResult

logger = logging.getLogger(__name__)

MUJI_BASE_URL = "https://www.muji.com/jp/ja/store"
MUJI_SEARCH_URL = f"{MUJI_BASE_URL}/search/cmdty"
MUJI_ITEM_URL = f"{MUJI_BASE_URL}/cmdty/detail"

MUJI_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en;q=0.9",
}

RATE_LIMIT_INTERVAL = 0.5  # 2 req/sec


class MujiClient(SourceSearcher):
    """無印良品ネットストア スクレイパー."""

    def __init__(
        self,
        *,
        timeout: float = 20.0,
        max_retries: int = 3,
    ) -> None:
        self._timeout = timeout
        self._max_retries = max_retries
        self._client: httpx.AsyncClient | None = None
        self._last_request_time: float = 0

    @property
    def site_name(self) -> str:
        return "muji"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=MUJI_HEADERS,
                timeout=self._timeout,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _rate_limit(self) -> None:
        """レートリミットを遵守する."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < RATE_LIMIT_INTERVAL:
            await asyncio.sleep(RATE_LIMIT_INTERVAL - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()

    async def _fetch(self, url: str, params: dict | None = None) -> str:
        """HTTPリクエストをリトライ付きで送信する."""
        await self._rate_limit()
        client = await self._get_client()
        for attempt in range(self._max_retries):
            try:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                return resp.text
            except httpx.HTTPError as e:
                logger.warning("Muji fetch attempt %d failed for %s: %s", attempt + 1, url, e)
                if attempt == self._max_retries - 1:
                    raise
        raise RuntimeError("Unreachable")

    async def search(self, query: str, *, max_results: int = 10) -> SourceSearchResult:
        """無印良品で商品を検索する."""
        params = {
            "searchWord": query,
            "pageSize": min(max_results, 60),
        }

        try:
            html = await self._fetch(MUJI_SEARCH_URL, params=params)
        except Exception as e:
            logger.error("無印良品検索失敗: %s", e)
            return SourceSearchResult(query=query, source_site=self.site_name)

        products = self._parse_search_results(html)
        logger.info("無印良品検索 '%s': %d 件取得", query, len(products))
        return SourceSearchResult(query=query, source_site=self.site_name, products=products)

    async def get_item(self, item_code: str) -> SourceProduct | None:
        """商品コードから商品情報を取得する."""
        url = f"{MUJI_ITEM_URL}/{item_code}"
        try:
            html = await self._fetch(url)
        except Exception as e:
            logger.error("無印良品商品取得失敗 (%s): %s", item_code, e)
            return None

        return self._parse_item_page(html, item_code, url)

    def _parse_search_results(self, html: str) -> list[SourceProduct]:
        """検索結果HTMLをパースする."""
        soup = BeautifulSoup(html, "lxml")
        products: list[SourceProduct] = []

        # Search result items - multiple possible selectors
        items = soup.select("li.product-tile, div.product-tile, article.product-item")
        if not items:
            # Fallback: try generic product containers
            items = soup.select("[data-product-id], .search-result-item")

        for item in items:
            product = self._parse_search_item(item)
            if product:
                products.append(product)

        return products

    def _parse_search_item(self, item: Tag) -> SourceProduct | None:
        """検索結果の個別アイテムをパースする."""
        # Title
        title_el = item.select_one("h3, h4, .product-name, .product-title, a[title]")
        if not title_el:
            return None
        title = title_el.get_text(strip=True)
        if not title:
            return None

        # Item code from data attribute or link
        item_code = self._extract_item_code(item)
        if not item_code:
            return None

        # Price
        price = self._parse_price(item)
        if not price:
            return None

        # URL
        link_el = item.select_one("a[href]")
        url = ""
        if link_el:
            href = link_el.get("href", "")
            if isinstance(href, list):
                href = href[0] if href else ""
            url = href if href.startswith("http") else f"https://www.muji.com{href}"

        # Image
        image_url = self._parse_image(item)

        # Category
        category = None
        cat_el = item.select_one(".product-category, .category-name")
        if cat_el:
            category = cat_el.get_text(strip=True)

        return SourceProduct(
            item_code=item_code,
            source_site="muji",
            title=title,
            price_jpy=price,
            url=url,
            image_url=image_url,
            category=category,
        )

    def _parse_item_page(self, html: str, item_code: str, url: str) -> SourceProduct | None:
        """商品詳細ページをパースする."""
        soup = BeautifulSoup(html, "lxml")

        # Title
        title_el = soup.select_one("h1, .product-name, .item-name")
        if not title_el:
            return None
        title = title_el.get_text(strip=True)
        if not title:
            return None

        # Price
        price = self._parse_price(soup)
        if not price:
            return None

        # Image
        image_url = self._parse_image(soup)

        # Category from breadcrumb
        category = None
        breadcrumbs = soup.select(".breadcrumb li, nav.breadcrumb a")
        if len(breadcrumbs) >= 2:
            category = breadcrumbs[-2].get_text(strip=True)

        # Availability
        availability = True
        stock_el = soup.select_one(".out-of-stock, .soldout")
        if stock_el:
            availability = False

        # Review
        review_count = None
        rating = None
        review_el = soup.select_one(".review-count, [data-review-count]")
        if review_el:
            count_text = review_el.get_text(strip=True)
            match = re.search(r"\d+", count_text)
            if match:
                review_count = int(match.group())

        rating_el = soup.select_one(".rating, [data-rating]")
        if rating_el:
            rating_attr = rating_el.get("data-rating")
            if rating_attr:
                try:
                    rating = float(rating_attr if isinstance(rating_attr, str) else rating_attr[0])
                except (ValueError, IndexError):
                    pass

        return SourceProduct(
            item_code=item_code,
            source_site="muji",
            title=title,
            price_jpy=price,
            url=url,
            image_url=image_url,
            category=category,
            availability=availability,
            review_count=review_count,
            rating=rating,
        )

    @staticmethod
    def _extract_item_code(item: Tag) -> str | None:
        """商品コードを抽出する."""
        # data attribute
        for attr in ("data-product-id", "data-item-code", "data-sku"):
            val = item.get(attr)
            if val:
                return val if isinstance(val, str) else str(val[0])

        # From link URL (e.g., /cmdty/detail/4550344294956)
        link_el = item.select_one("a[href]")
        if link_el:
            href = link_el.get("href", "")
            if isinstance(href, list):
                href = href[0] if href else ""
            match = re.search(r"/detail/(\d{10,15})", href)
            if match:
                return match.group(1)
            # JAN code pattern in URL
            match = re.search(r"/(\d{13})", href)
            if match:
                return match.group(1)

        return None

    @staticmethod
    def _parse_price(container: Tag) -> int | None:
        """価格を抽出する."""
        # Try common price selectors
        for selector in (
            ".price, .product-price, .sales-price",
            "span[class*='price']",
            "[data-price]",
        ):
            price_el = container.select_one(selector)
            if price_el:
                # Check data attribute first
                data_price = price_el.get("data-price")
                if data_price:
                    try:
                        val = data_price if isinstance(data_price, str) else str(data_price[0])
                        return int(float(val))
                    except (ValueError, IndexError):
                        pass

                # Parse text
                text = price_el.get_text(strip=True)
                # Remove yen sign and commas
                match = re.search(r"[\d,]+", text.replace("¥", "").replace("￥", "").replace("円", ""))
                if match:
                    try:
                        return int(match.group().replace(",", ""))
                    except ValueError:
                        pass

        return None

    @staticmethod
    def _parse_image(container: Tag) -> str | None:
        """画像URLを抽出する."""
        img_el = container.select_one("img.product-image, img[src*='muji'], img")
        if not img_el:
            return None
        src = img_el.get("src") or img_el.get("data-src")
        if isinstance(src, list):
            src = src[0] if src else None
        return src
