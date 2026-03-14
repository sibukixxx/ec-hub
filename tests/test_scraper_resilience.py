"""スクレイパー耐障害性のテスト."""

from unittest.mock import AsyncMock, patch

import pytest

from ec_hub.scrapers.ebay import EbayScraper
from ec_hub.scrapers.selectors import load_selectors


class TestSelectorConfig:
    """セレクタ外部設定のテスト."""

    def test_load_default_selectors(self):
        selectors = load_selectors()
        assert selectors.search.item is not None
        assert selectors.search.title is not None
        assert selectors.search.price is not None

    def test_load_selectors_from_file(self, tmp_path):
        yaml_content = """
search:
  item: "li.custom-item"
  title: "div.custom-title span"
  title_fallback: "div.custom-title"
  link: "a.custom-link"
  price: "span.custom-price"
  image: "img.custom-img"
  shipping: "span.custom-shipping"
  condition: "span.custom-condition"
  result_count: "h1.custom-count span"

item_page:
  title: "h1.custom-title span"
  price_primary: "div.custom-price span"
  price_fallback: "span[itemprop='price']"
  image_primary: "img.custom-img"
  image_fallback: "div.custom-carousel img"
  seller_primary: "span.custom-seller"
  seller_fallback: "div.custom-seller a span"
  condition_primary: "span.custom-condition"
  condition_fallback: "div.custom-condition span"
"""
        config_file = tmp_path / "selectors.yaml"
        config_file.write_text(yaml_content)

        selectors = load_selectors(str(config_file))
        assert selectors.search.item == "li.custom-item"
        assert selectors.search.title == "div.custom-title span"
        assert selectors.item_page.title == "h1.custom-title span"

    def test_selector_config_has_all_required_fields(self):
        selectors = load_selectors()
        # Search selectors
        assert selectors.search.item
        assert selectors.search.title
        assert selectors.search.link
        assert selectors.search.price
        assert selectors.search.shipping
        assert selectors.search.condition
        assert selectors.search.result_count
        # Item page selectors
        assert selectors.item_page.title
        assert selectors.item_page.price_primary or selectors.item_page.price_fallback


class TestScraperWithSelectors:
    """セレクタ設定を使ったスクレイパーのテスト."""

    def test_scraper_accepts_custom_selectors(self):
        selectors = load_selectors()
        scraper = EbayScraper(selectors=selectors)
        assert scraper._selectors is not None

    def test_parse_search_results_with_selectors(self):
        scraper = EbayScraper()
        html = """
        <html><body>
        <h1 class="srp-controls__count-heading"><span class="BOLD">5</span> results</h1>
        <ul class="srp-results">
            <li class="s-item">
                <div class="s-item__title"><span role="heading">Product A</span></div>
                <a class="s-item__link" href="https://www.ebay.com/itm/100100100">link</a>
                <span class="s-item__price">$25.00</span>
            </li>
        </ul>
        </body></html>
        """
        result = scraper._parse_search_results(html, "test", 1)
        assert len(result.products) == 1
        assert result.products[0].item_id == "100100100"


class TestSearchResultValidation:
    """検索結果の妥当性チェックのテスト."""

    def test_validate_result_returns_true_for_valid_result(self):
        scraper = EbayScraper()
        html = """
        <html><body>
        <h1 class="srp-controls__count-heading"><span class="BOLD">100</span> results</h1>
        <ul class="srp-results">
            <li class="s-item">
                <div class="s-item__title"><span role="heading">Product A</span></div>
                <a class="s-item__link" href="https://www.ebay.com/itm/111">link</a>
                <span class="s-item__price">$25.00</span>
            </li>
        </ul>
        </body></html>
        """
        result = scraper._parse_search_results(html, "keyboard", 1)
        issues = scraper.validate_result(result)
        assert len(issues) == 0

    def test_validate_result_detects_zero_products_with_nonzero_count(self):
        scraper = EbayScraper()
        html = """
        <html><body>
        <h1 class="srp-controls__count-heading"><span class="BOLD">500</span> results</h1>
        <ul class="srp-results"></ul>
        </body></html>
        """
        result = scraper._parse_search_results(html, "keyboard", 1)
        issues = scraper.validate_result(result)
        assert len(issues) > 0
        assert any("0 products" in issue.lower() or "0件" in issue for issue in issues)

    def test_validate_result_detects_all_null_prices(self):
        scraper = EbayScraper()
        html = """
        <html><body>
        <h1 class="srp-controls__count-heading"><span class="BOLD">2</span> results</h1>
        <ul class="srp-results">
            <li class="s-item">
                <div class="s-item__title"><span role="heading">Product A</span></div>
                <a class="s-item__link" href="https://www.ebay.com/itm/111">link</a>
            </li>
            <li class="s-item">
                <div class="s-item__title"><span role="heading">Product B</span></div>
                <a class="s-item__link" href="https://www.ebay.com/itm/222">link</a>
            </li>
        </ul>
        </body></html>
        """
        result = scraper._parse_search_results(html, "keyboard", 1)
        issues = scraper.validate_result(result)
        assert any("price" in issue.lower() or "価格" in issue for issue in issues)


class TestScraperCircuitBreakerIntegration:
    """スクレイパーとサーキットブレーカーの統合テスト."""

    def test_scraper_has_circuit_breaker(self):
        scraper = EbayScraper()
        assert scraper._circuit_breaker is not None

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_consecutive_failures(self):
        from ec_hub.scrapers.circuit_breaker import CircuitBreakerOpenError

        scraper = EbayScraper(max_retries=1, circuit_breaker_threshold=2)
        async with scraper:
            with patch.object(scraper, "_fetch", side_effect=RuntimeError("network error")):
                with pytest.raises(RuntimeError):
                    await scraper.search("test1")
                with pytest.raises(RuntimeError):
                    await scraper.search("test2")

            with pytest.raises(CircuitBreakerOpenError):
                await scraper.search("test3")


class TestScraperNotifierIntegration:
    """スクレイパーと通知の統合テスト."""

    @pytest.mark.asyncio
    async def test_notifies_on_parse_validation_failure(self):
        notifier = AsyncMock()
        notifier.send = AsyncMock(return_value=True)
        scraper = EbayScraper(notifier=notifier)

        html = """
        <html><body>
        <h1 class="srp-controls__count-heading"><span class="BOLD">500</span> results</h1>
        <ul class="srp-results"></ul>
        </body></html>
        """
        result = scraper._parse_search_results(html, "keyboard", 1)
        issues = scraper.validate_result(result)

        if issues:
            await scraper._notify_parse_issues(issues)

        notifier.send.assert_called_once()
        call_msg = notifier.send.call_args[0][0]
        assert "スクレイパー" in call_msg or "scraper" in call_msg.lower()
