"""スクレイパー耐障害性のテスト."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import yaml
from bs4 import BeautifulSoup

from ec_hub.models import Product, SearchResult
from ec_hub.scrapers.circuit_breaker import CircuitBreaker, CircuitBreakerOpen, CircuitState
from ec_hub.scrapers.ebay import EbayScraper
from ec_hub.scrapers.selectors import EbaySelectors, load_selectors
from ec_hub.scrapers.validator import ScrapeValidator

# --- フェーズ1: セレクタ外部設定 ---


class TestEbaySelectors:
    """EbaySelectors モデルのテスト."""

    def test_default_selectors_have_search_item(self):
        """デフォルトセレクタに検索アイテムのセレクタが含まれている."""
        selectors = EbaySelectors()
        assert selectors.search_item == "li.s-item"

    def test_default_selectors_have_title(self):
        """デフォルトセレクタにタイトルのセレクタが含まれている."""
        selectors = EbaySelectors()
        assert selectors.search_title == "div.s-item__title span[role='heading']"

    def test_default_selectors_have_price(self):
        """デフォルトセレクタに価格のセレクタが含まれている."""
        selectors = EbaySelectors()
        assert selectors.search_price == "span.s-item__price"

    def test_default_selectors_have_link(self):
        """デフォルトセレクタにリンクのセレクタが含まれている."""
        selectors = EbaySelectors()
        assert selectors.search_link == "a.s-item__link"

    def test_default_selectors_have_item_page_title(self):
        """デフォルトセレクタに商品ページタイトルのセレクタが含まれている."""
        selectors = EbaySelectors()
        assert selectors.item_title == "h1.x-item-title__mainTitle span"

    def test_custom_selectors_override_defaults(self):
        """カスタムセレクタでデフォルトを上書きできる."""
        selectors = EbaySelectors(search_item="div.custom-item")
        assert selectors.search_item == "div.custom-item"
        # Other defaults remain
        assert selectors.search_price == "span.s-item__price"


class TestLoadSelectors:
    """load_selectors 関数のテスト."""

    def test_load_from_yaml(self, tmp_path: Path):
        """YAMLファイルからセレクタを読み込める."""
        config = {
            "search_item": "div.new-item",
            "search_title": "h2.new-title",
        }
        yaml_path = tmp_path / "selectors.yaml"
        yaml_path.write_text(yaml.dump(config), encoding="utf-8")

        selectors = load_selectors(yaml_path)
        assert selectors.search_item == "div.new-item"
        assert selectors.search_title == "h2.new-title"
        # Non-specified fields keep defaults
        assert selectors.search_price == "span.s-item__price"

    def test_load_returns_default_when_file_not_found(self):
        """ファイルが見つからない場合はデフォルトを返す."""
        selectors = load_selectors(Path("/nonexistent/selectors.yaml"))
        assert selectors == EbaySelectors()

    def test_load_returns_default_when_file_is_empty(self, tmp_path: Path):
        """空ファイルの場合はデフォルトを返す."""
        yaml_path = tmp_path / "selectors.yaml"
        yaml_path.write_text("", encoding="utf-8")

        selectors = load_selectors(yaml_path)
        assert selectors == EbaySelectors()


class TestEbayScraperWithSelectors:
    """EbayScraper がセレクタ設定を使ってパースするテスト."""

    def test_scraper_accepts_custom_selectors(self):
        """EbayScraper にカスタムセレクタを渡せる."""
        custom = EbaySelectors(search_item="div.custom-item")
        scraper = EbayScraper(selectors=custom)
        assert scraper._selectors.search_item == "div.custom-item"

    def test_scraper_uses_default_selectors_when_not_provided(self):
        """セレクタ未指定時はデフォルトが使われる."""
        scraper = EbayScraper()
        assert scraper._selectors == EbaySelectors()

    def test_parse_search_item_with_custom_selectors(self):
        """カスタムセレクタで検索アイテムをパースできる."""
        custom = EbaySelectors(
            search_title="h3.custom-title",
            search_link="a.custom-link",
            search_price="span.custom-price",
            search_shipping="span.custom-shipping",
            search_condition="span.custom-condition",
        )
        html = """
        <li class="s-item">
            <h3 class="custom-title">Custom Title Product</h3>
            <a class="custom-link" href="https://www.ebay.com/itm/555666777">link</a>
            <span class="custom-price">$29.99</span>
            <span class="custom-shipping">Free shipping</span>
            <span class="custom-condition">Brand New</span>
        </li>
        """
        soup = BeautifulSoup(html, "lxml")
        item = soup.select_one("li.s-item")
        scraper = EbayScraper(selectors=custom)
        product = scraper._parse_search_item(item)

        assert product is not None
        assert product.title == "Custom Title Product"
        assert product.price == 29.99
        assert product.item_id == "555666777"

    def test_parse_item_page_with_custom_selectors(self):
        """カスタムセレクタで商品詳細ページをパースできる."""
        custom = EbaySelectors(
            item_title="h2.custom-detail-title",
            item_price="span.custom-detail-price",
        )
        html = """
        <html><body>
            <h2 class="custom-detail-title">Detail Title</h2>
            <span class="custom-detail-price">$99.99</span>
        </body></html>
        """
        scraper = EbayScraper(selectors=custom)
        product = scraper._parse_item_page(html, "123", "https://www.ebay.com/itm/123")

        assert product is not None
        assert product.title == "Detail Title"
        assert product.price == 99.99


# --- フェーズ2: サーキットブレーカー ---


class TestCircuitBreaker:
    """CircuitBreaker の状態遷移テスト."""

    def test_initial_state_is_closed(self):
        """初期状態は CLOSED."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)
        assert cb.state == CircuitState.CLOSED

    def test_stays_closed_below_threshold(self):
        """閾値未満の失敗では CLOSED のまま."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    def test_opens_at_threshold(self):
        """閾値到達で OPEN に遷移."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_open_raises_on_check(self):
        """OPEN 状態で allow_request すると CircuitBreakerOpen が送出される."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        try:
            cb.allow_request()
            assert False, "Expected CircuitBreakerOpen"
        except CircuitBreakerOpen:
            pass

    def test_transitions_to_half_open_after_timeout(self):
        """recovery_timeout 後に HALF_OPEN に遷移."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_allows_one_request(self):
        """HALF_OPEN 状態では allow_request が通る."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        time.sleep(0.15)

        # Should not raise
        cb.allow_request()

    def test_half_open_success_closes(self):
        """HALF_OPEN で成功すると CLOSED に戻る."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        time.sleep(0.15)

        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self):
        """HALF_OPEN で失敗すると再び OPEN になる."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_success_resets_failure_count(self):
        """成功すると失敗カウントがリセットされる."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        # Only 1 failure after reset, still CLOSED
        assert cb.state == CircuitState.CLOSED


class TestEbayScraperCircuitBreaker:
    """EbayScraper にサーキットブレーカーを統合したテスト."""

    def test_scraper_accepts_circuit_breaker(self):
        """EbayScraper に CircuitBreaker を渡せる."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)
        scraper = EbayScraper(circuit_breaker=cb)
        assert scraper._circuit_breaker is cb

    def test_scraper_creates_default_circuit_breaker_when_not_provided(self):
        """未指定時はデフォルトの CircuitBreaker が作成されない（None）."""
        scraper = EbayScraper()
        assert scraper._circuit_breaker is None

    @pytest.mark.asyncio
    async def test_fetch_raises_circuit_breaker_open_when_open(self):
        """サーキットブレーカーが OPEN 時に _fetch が CircuitBreakerOpen を送出する."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        cb.record_failure()  # OPEN にする
        scraper = EbayScraper(circuit_breaker=cb)

        with pytest.raises(CircuitBreakerOpen):
            await scraper._fetch("https://www.ebay.com/sch/i.html")

    @pytest.mark.asyncio
    async def test_fetch_records_failure_on_http_error(self):
        """HTTP エラー時にサーキットブレーカーに失敗を記録する."""
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)
        scraper = EbayScraper(circuit_breaker=cb, max_retries=1)

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=httpx.Request("GET", "https://example.com"), response=httpx.Response(500)
        )

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.is_closed = False
        scraper._client = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            await scraper._fetch("https://www.ebay.com/sch/i.html")

        assert cb._failure_count == 1

    @pytest.mark.asyncio
    async def test_fetch_records_success_on_ok_response(self):
        """成功レスポンス時にサーキットブレーカーに成功を記録する."""
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)
        cb._failure_count = 2  # Simulate previous failures
        scraper = EbayScraper(circuit_breaker=cb)

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.text = "<html></html>"

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.is_closed = False
        scraper._client = mock_client

        await scraper._fetch("https://www.ebay.com/sch/i.html")

        assert cb._failure_count == 0


# --- フェーズ3: パース失敗アラート + 妥当性チェック ---


class TestScrapeValidator:
    """ScrapeValidator のテスト."""

    def _make_search_result(self, *, total: int = 10, product_count: int = 5) -> SearchResult:
        """テスト用 SearchResult を生成する."""
        products = [
            Product(item_id=str(i), title=f"Product {i}", price=10.0 * i, url=f"https://ebay.com/itm/{i}")
            for i in range(product_count)
        ]
        return SearchResult(query="test", total_results=total, page=1, products=products)

    def test_valid_result_passes(self):
        """正常な検索結果はバリデーションを通過する."""
        validator = ScrapeValidator()
        result = self._make_search_result(total=10, product_count=5)
        validation = validator.validate_search_result(result)
        assert validation.is_valid is True
        assert len(validation.warnings) == 0

    def test_zero_products_is_warning(self):
        """商品0件はバリデーション警告."""
        validator = ScrapeValidator()
        result = self._make_search_result(total=100, product_count=0)
        validation = validator.validate_search_result(result)
        assert validation.is_valid is False
        assert any("0 products" in w for w in validation.warnings)

    def test_zero_total_with_products_is_warning(self):
        """total_results=0 なのに商品がある場合は警告."""
        validator = ScrapeValidator()
        result = self._make_search_result(total=0, product_count=5)
        validation = validator.validate_search_result(result)
        assert validation.is_valid is False
        assert any("mismatch" in w.lower() for w in validation.warnings)

    def test_all_products_no_price_is_warning(self):
        """全商品の価格がNoneの場合は警告."""
        validator = ScrapeValidator()
        products = [
            Product(item_id=str(i), title=f"Product {i}", price=None, url=f"https://ebay.com/itm/{i}") for i in range(5)
        ]
        result = SearchResult(query="test", total_results=5, page=1, products=products)
        validation = validator.validate_search_result(result)
        assert validation.is_valid is False
        assert any("price" in w.lower() for w in validation.warnings)

    def test_parse_failure_detected(self):
        """パース失敗を検知する."""
        validator = ScrapeValidator()
        html = "<html><body><p>Blocked or changed page</p></body></html>"
        validation = validator.validate_html(html)
        assert validation.is_valid is False
        assert any("parse" in w.lower() or "no items" in w.lower() for w in validation.warnings)


class TestEbayScraperValidation:
    """EbayScraper にバリデーション・通知を統合したテスト."""

    def test_scraper_accepts_validator_and_notifier(self):
        """EbayScraper に validator と notifier を渡せる."""
        from ec_hub.modules.notifier import Notifier

        validator = ScrapeValidator()
        notifier = Notifier(settings={"line": {}})
        scraper = EbayScraper(validator=validator, notifier=notifier)
        assert scraper._validator is validator
        assert scraper._notifier is notifier

    def test_scraper_defaults_to_no_validator_and_notifier(self):
        """未指定時は None."""
        scraper = EbayScraper()
        assert scraper._validator is None
        assert scraper._notifier is None

    @pytest.mark.asyncio
    async def test_search_validates_result_and_notifies_on_failure(self):
        """検索結果バリデーション失敗時に通知が送信される."""
        from ec_hub.modules.notifier import Notifier

        notifier = AsyncMock(spec=Notifier)
        notifier.is_configured = True
        validator = ScrapeValidator()
        scraper = EbayScraper(validator=validator, notifier=notifier)

        # Mock _fetch to return HTML with no items
        empty_html = "<html><body><p>No results</p></body></html>"
        scraper._fetch = AsyncMock(return_value=empty_html)

        await scraper.search("test query")

        # Notifier should have been called with scrape alert
        notifier.send.assert_called_once()
        call_msg = notifier.send.call_args[0][0]
        assert "scraper" in call_msg.lower() or "alert" in call_msg.lower() or "warning" in call_msg.lower()

    @pytest.mark.asyncio
    async def test_search_does_not_notify_on_valid_result(self):
        """正常な検索結果では通知を送信しない."""
        from ec_hub.modules.notifier import Notifier

        notifier = AsyncMock(spec=Notifier)
        notifier.is_configured = True
        validator = ScrapeValidator()
        scraper = EbayScraper(validator=validator, notifier=notifier)

        # Mock _fetch to return HTML with items
        html = """
        <html><body>
            <h1 class="srp-controls__count-heading"><span class="BOLD">5</span></h1>
            <li class="s-item">
                <div class="s-item__title"><span role="heading">Product A</span></div>
                <a class="s-item__link" href="https://www.ebay.com/itm/111">link</a>
                <span class="s-item__price">$10.00</span>
            </li>
        </body></html>
        """
        scraper._fetch = AsyncMock(return_value=html)

        await scraper.search("test query")

        notifier.send.assert_not_called()
