"""eBay商品スクレイパー."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

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
from ec_hub.scrapers.selectors import SelectorConfig, load_selectors

if TYPE_CHECKING:
    from ec_hub.modules.notifier import Notifier

logger = logging.getLogger(__name__)

EBAY_SEARCH_URL = "https://www.ebay.com/sch/i.html"
EBAY_ITEM_URL = "https://www.ebay.com/itm/"

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
        selectors: SelectorConfig | None = None,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: float = 60.0,
        notifier: Notifier | None = None,
    ) -> None:
        self._timeout = timeout
        self._max_retries = max_retries
        self._base_url = f"https://www.ebay.{site}"
        self._client: httpx.AsyncClient | None = None
        self._selectors = selectors or load_selectors()
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=circuit_breaker_threshold,
            recovery_timeout=circuit_breaker_timeout,
        )
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
        client = await self._get_client()
        for attempt in range(self._max_retries):
            try:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                return resp.text
            except httpx.HTTPError as e:
                logger.warning("Fetch attempt %d failed for %s: %s", attempt + 1, url, e)
                if attempt == self._max_retries - 1:
                    raise
        raise RuntimeError("Unreachable")

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

        Raises:
            CircuitBreakerOpenError: サーキットブレーカーが OPEN 状態の場合
        """
        self._circuit_breaker.ensure_closed()

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
        try:
            html = await self._fetch(url, params=params)
            result = self._parse_search_results(html, query, page)
            self._circuit_breaker.record_success()
            return result
        except Exception:
            self._circuit_breaker.record_failure()
            raise

    def _parse_search_results(self, html: str, query: str, page: int) -> SearchResult:
        """検索結果HTMLをパースする."""
        soup = BeautifulSoup(html, "lxml")
        products: list[Product] = []
        sel = self._selectors.search

        result_count = 0
        count_el = soup.select_one(sel.result_count)
        if count_el:
            count_text = count_el.get_text(strip=True).replace(",", "")
            try:
                result_count = int(count_text)
            except ValueError:
                pass

        items = soup.select(sel.item)
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
        sel = self._selectors.search

        title_el = item.select_one(sel.title)
        if not title_el:
            title_el = item.select_one(sel.title_fallback)
        if not title_el:
            return None

        title = title_el.get_text(strip=True)
        if title.lower() in ("shop on ebay", ""):
            return None

        link_el = item.select_one(sel.link)
        url = link_el["href"] if link_el and link_el.get("href") else ""
        if not isinstance(url, str):
            url = str(url)

        item_id = self._extract_item_id(url)
        if not item_id:
            return None

        price = self._parse_price(item)

        img_el = item.select_one(sel.image)
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
        sel = self._selectors.search
        price_el = item.select_one(sel.price)
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
        sel = self._selectors.search
        shipping_el = item.select_one(sel.shipping)
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

    def _parse_condition(self, item: Tag) -> ListingCondition:
        """商品状態をパースする."""
        sel = self._selectors.search
        cond_el = item.select_one(sel.condition)
        if not cond_el:
            return ListingCondition.NOT_SPECIFIED
        text = cond_el.get_text(strip=True).lower()
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

    async def get_item(self, item_id: str) -> Product | None:
        """商品IDから詳細情報を取得する.

        Args:
            item_id: eBay商品ID

        Returns:
            Product or None

        Raises:
            CircuitBreakerOpenError: サーキットブレーカーが OPEN 状態の場合
        """
        self._circuit_breaker.ensure_closed()

        url = f"{self._base_url}/itm/{item_id}"
        try:
            html = await self._fetch(url)
            result = self._parse_item_page(html, item_id, url)
            self._circuit_breaker.record_success()
            return result
        except Exception:
            self._circuit_breaker.record_failure()
            raise

    def _parse_item_page(self, html: str, item_id: str, url: str) -> Product | None:
        """商品詳細ページHTMLをパースする."""
        soup = BeautifulSoup(html, "lxml")
        sel = self._selectors.item_page

        title_el = soup.select_one(sel.title)
        if not title_el:
            return None
        title = title_el.get_text(strip=True)

        price = None
        price_el = soup.select_one(sel.price_primary)
        if not price_el:
            price_el = soup.select_one(sel.price_fallback)
        if price_el:
            price_text = price_el.get_text(strip=True)
            match = re.search(r"[\d,]+\.?\d*", price_text.replace(",", ""))
            if match:
                try:
                    price = float(match.group())
                except ValueError:
                    pass

        img_el = soup.select_one(sel.image_primary)
        if not img_el:
            img_el = soup.select_one(sel.image_fallback)
        image_url = None
        if img_el:
            image_url = img_el.get("src") or img_el.get("data-src")
            if isinstance(image_url, list):
                image_url = image_url[0] if image_url else None

        seller = None
        seller_el = soup.select_one(sel.seller_primary)
        if not seller_el:
            seller_el = soup.select_one(sel.seller_fallback)
        if seller_el:
            seller = SellerInfo(name=seller_el.get_text(strip=True))

        condition = ListingCondition.NOT_SPECIFIED
        cond_el = soup.select_one(sel.condition_primary)
        if not cond_el:
            cond_el = soup.select_one(sel.condition_fallback)
        if cond_el:
            cond_text = cond_el.get_text(strip=True).lower()
            if "new" in cond_text and "open" not in cond_text:
                condition = ListingCondition.NEW
            elif "refurbished" in cond_text:
                condition = ListingCondition.REFURBISHED
            elif "used" in cond_text or "pre-owned" in cond_text:
                condition = ListingCondition.USED

        return Product(
            item_id=item_id,
            title=title,
            price=price,
            url=url,
            image_url=image_url,
            seller=seller,
            condition=condition,
        )

    def validate_result(self, result: SearchResult) -> list[str]:
        """検索結果の妥当性をチェックする.

        Returns:
            問題点のリスト。空ならば正常。
        """
        issues: list[str] = []

        if result.total_results > 0 and len(result.products) == 0:
            issues.append(
                f"検索結果 {result.total_results} 件と表示されたが、パースされた商品は0件。"
                "CSSセレクタが古い可能性があります。"
            )

        if result.products and all(p.price is None for p in result.products):
            issues.append(
                f"全 {len(result.products)} 件の商品で価格が取得できませんでした。"
                "価格セレクタが古い可能性があります。"
            )

        return issues

    async def _notify_parse_issues(self, issues: list[str]) -> None:
        """パース問題をLINE通知する."""
        if not self._notifier:
            for issue in issues:
                logger.warning("スクレイパー検証問題: %s", issue)
            return

        message = "[ec-hub] スクレイパー検証アラート\n" + "\n".join(f"- {issue}" for issue in issues)
        await self._notifier.send(message)
