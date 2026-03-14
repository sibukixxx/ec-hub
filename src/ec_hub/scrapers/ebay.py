"""eBay商品スクレイパー."""

from __future__ import annotations

import logging
import re
from typing import Protocol, runtime_checkable

import httpx
from bs4 import BeautifulSoup, Tag

from ec_hub.models import (
    ListingCondition,
    Product,
    SearchResult,
    SellerInfo,
    ShippingInfo,
)
from ec_hub.scrapers.circuit_breaker import CircuitBreaker
from ec_hub.scrapers.selectors import EbaySelectors
from ec_hub.scrapers.validator import ScrapeValidator

logger = logging.getLogger(__name__)

EBAY_SEARCH_URL = "https://www.ebay.com/sch/i.html"
EBAY_ITEM_URL = "https://www.ebay.com/itm/"


@runtime_checkable
class Notifiable(Protocol):
    """通知送信プロトコル."""

    async def send(self, message: str) -> bool: ...


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class EbayScraper:
    """eBay検索結果・商品ページのスクレイパー."""

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        max_retries: int = 3,
        site: str = "com",
        selectors: EbaySelectors | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        validator: ScrapeValidator | None = None,
        notifier: Notifiable | None = None,
    ) -> None:
        self._timeout = timeout
        self._max_retries = max_retries
        self._base_url = f"https://www.ebay.{site}"
        self._client: httpx.AsyncClient | None = None
        self._selectors = selectors or EbaySelectors()
        self._circuit_breaker = circuit_breaker
        self._validator = validator
        self._notifier = notifier

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=DEFAULT_HEADERS,
                timeout=self._timeout,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> EbayScraper:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def _fetch(self, url: str, params: dict | None = None) -> str:
        if self._circuit_breaker:
            self._circuit_breaker.allow_request()

        client = await self._get_client()
        for attempt in range(self._max_retries):
            try:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                if self._circuit_breaker:
                    self._circuit_breaker.record_success()
                return resp.text
            except httpx.HTTPError as e:
                logger.warning("Fetch attempt %d failed for %s: %s", attempt + 1, url, e)
                if attempt == self._max_retries - 1:
                    if self._circuit_breaker:
                        self._circuit_breaker.record_failure()
                    raise
        raise RuntimeError("Unreachable")

    async def _validate_and_notify(self, html: str, result: SearchResult) -> None:
        """検索結果をバリデーションし、問題があれば通知する."""
        if not self._validator:
            return

        warnings: list[str] = []

        html_validation = self._validator.validate_html(html, item_selector=self._selectors.search_item)
        warnings.extend(html_validation.warnings)

        result_validation = self._validator.validate_search_result(result)
        warnings.extend(result_validation.warnings)

        if warnings and self._notifier:
            msg = "[ec-hub] Scraper warning:\n" + "\n".join(f"- {w}" for w in warnings)
            logger.warning("Scraper validation warnings: %s", warnings)
            await self._notifier.send(msg)

    async def search(
        self,
        query: str,
        *,
        page: int = 1,
        min_price: float | None = None,
        max_price: float | None = None,
        condition: ListingCondition | None = None,
        sort: str | None = None,
    ) -> SearchResult:
        """eBayで商品を検索する.

        Args:
            query: 検索キーワード
            page: ページ番号
            min_price: 最低価格フィルタ
            max_price: 最高価格フィルタ
            condition: 商品状態フィルタ
            sort: ソート順 (例: "price_asc", "price_desc", "date_desc")

        Returns:
            SearchResult: 検索結果
        """
        params: dict[str, str] = {
            "_nkw": query,
            "_pgn": str(page),
        }

        if min_price is not None:
            params["_udlo"] = str(min_price)
        if max_price is not None:
            params["_udhi"] = str(max_price)

        if condition is not None:
            condition_map = {
                ListingCondition.NEW: "1000",
                ListingCondition.OPEN_BOX: "1500",
                ListingCondition.REFURBISHED: "2000",
                ListingCondition.USED: "3000",
                ListingCondition.FOR_PARTS: "7000",
            }
            cond_val = condition_map.get(condition)
            if cond_val:
                params["LH_ItemCondition"] = cond_val

        sort_map = {
            "price_asc": "15",
            "price_desc": "16",
            "date_desc": "10",
            "best_match": "12",
            "ending_soonest": "1",
            "newly_listed": "10",
        }
        if sort and sort in sort_map:
            params["_sop"] = sort_map[sort]

        url = f"{self._base_url}/sch/i.html"
        html = await self._fetch(url, params=params)
        result = self._parse_search_results(html, query, page)
        await self._validate_and_notify(html, result)
        return result

    def _parse_search_results(self, html: str, query: str, page: int) -> SearchResult:
        """検索結果HTMLをパースする."""
        soup = BeautifulSoup(html, "lxml")
        products: list[Product] = []

        result_count = 0
        count_el = soup.select_one(self._selectors.search_result_count)
        if count_el:
            count_text = count_el.get_text(strip=True).replace(",", "")
            try:
                result_count = int(count_text)
            except ValueError:
                pass

        items = soup.select(self._selectors.search_item)
        for item in items:
            product = self._parse_search_item(item)
            if product:
                products.append(product)

        return SearchResult(
            query=query,
            total_results=result_count,
            page=page,
            products=products,
        )

    def _parse_search_item(self, item: Tag) -> Product | None:
        """検索結果の個別アイテムをパースする."""
        sel = self._selectors
        title_el = item.select_one(sel.search_title)
        if not title_el:
            title_el = item.select_one(sel.search_title_fallback)
        if not title_el:
            return None

        title = title_el.get_text(strip=True)
        if title.lower() in ("shop on ebay", ""):
            return None

        link_el = item.select_one(sel.search_link)
        url = link_el["href"] if link_el and link_el.get("href") else ""
        if not isinstance(url, str):
            url = str(url)

        item_id = self._extract_item_id(url)
        if not item_id:
            return None

        price = self._parse_price(item)

        img_el = item.select_one(sel.search_image)
        image_url = None
        if img_el:
            image_url = img_el.get("src") or img_el.get("data-src")
            if isinstance(image_url, list):
                image_url = image_url[0] if image_url else None

        shipping = self._parse_shipping(item)
        condition = self._parse_condition(item)

        return Product(
            item_id=item_id,
            title=title,
            price=price,
            url=url,
            image_url=image_url,
            shipping=shipping,
            condition=condition,
        )

    @staticmethod
    def _extract_item_id(url: str) -> str | None:
        """URLからeBay商品IDを抽出する."""
        match = re.search(r"/itm/(\d+)", url)
        if match:
            return match.group(1)
        match = re.search(r"item=(\d+)", url)
        if match:
            return match.group(1)
        return None

    def _parse_price(self, item: Tag) -> float | None:
        """価格をパースする."""
        price_el = item.select_one(self._selectors.search_price)
        if not price_el:
            return None
        price_text = price_el.get_text(strip=True)
        match = re.search(r"[\d,]+\.?\d*", price_text.replace(",", ""))
        if match:
            try:
                return float(match.group())
            except ValueError:
                return None
        return None

    def _parse_shipping(self, item: Tag) -> ShippingInfo:
        """配送情報をパースする."""
        shipping_el = item.select_one(self._selectors.search_shipping)
        if not shipping_el:
            return ShippingInfo()
        text = shipping_el.get_text(strip=True).lower()
        if "free" in text:
            return ShippingInfo(free_shipping=True, cost=0.0)
        match = re.search(r"[\d,]+\.?\d*", text.replace(",", ""))
        if match:
            try:
                return ShippingInfo(cost=float(match.group()))
            except ValueError:
                pass
        return ShippingInfo()

    @staticmethod
    def _classify_condition(text: str) -> ListingCondition:
        """テキストから商品状態を判定する."""
        text = text.lower()
        if "new" in text and "open" not in text:
            return ListingCondition.NEW
        if "open box" in text:
            return ListingCondition.OPEN_BOX
        if "refurbished" in text:
            return ListingCondition.REFURBISHED
        if "used" in text or "pre-owned" in text:
            return ListingCondition.USED
        if "parts" in text:
            return ListingCondition.FOR_PARTS
        return ListingCondition.NOT_SPECIFIED

    def _parse_condition(self, item: Tag) -> ListingCondition:
        """商品状態をパースする."""
        cond_el = item.select_one(self._selectors.search_condition)
        if not cond_el:
            return ListingCondition.NOT_SPECIFIED
        return self._classify_condition(cond_el.get_text(strip=True))

    async def get_item(self, item_id: str) -> Product | None:
        """商品IDから詳細情報を取得する.

        Args:
            item_id: eBay商品ID

        Returns:
            Product or None
        """
        url = f"{self._base_url}/itm/{item_id}"
        html = await self._fetch(url)
        return self._parse_item_page(html, item_id, url)

    def _parse_item_page(self, html: str, item_id: str, url: str) -> Product | None:
        """商品詳細ページHTMLをパースする."""
        soup = BeautifulSoup(html, "lxml")
        sel = self._selectors

        title_el = soup.select_one(sel.item_title)
        if not title_el:
            return None
        title = title_el.get_text(strip=True)

        price = None
        price_el = soup.select_one(sel.item_price)
        if not price_el:
            price_el = soup.select_one(sel.item_price_fallback)
        if price_el:
            price_text = price_el.get_text(strip=True)
            match = re.search(r"[\d,]+\.?\d*", price_text.replace(",", ""))
            if match:
                try:
                    price = float(match.group())
                except ValueError:
                    pass

        img_el = soup.select_one(sel.item_image)
        if not img_el:
            img_el = soup.select_one(sel.item_image_fallback)
        image_url = None
        if img_el:
            image_url = img_el.get("src") or img_el.get("data-src")
            if isinstance(image_url, list):
                image_url = image_url[0] if image_url else None

        seller = None
        seller_el = soup.select_one(sel.item_seller)
        if not seller_el:
            seller_el = soup.select_one(sel.item_seller_fallback)
        if seller_el:
            seller = SellerInfo(name=seller_el.get_text(strip=True))

        condition = ListingCondition.NOT_SPECIFIED
        cond_el = soup.select_one(sel.item_condition)
        if not cond_el:
            cond_el = soup.select_one(sel.item_condition_fallback)
        if cond_el:
            condition = self._classify_condition(cond_el.get_text(strip=True))

        return Product(
            item_id=item_id,
            title=title,
            price=price,
            url=url,
            image_url=image_url,
            seller=seller,
            condition=condition,
        )
