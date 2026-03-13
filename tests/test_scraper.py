"""スクレイパーのテスト."""

from ec_hub.models import ListingCondition
from ec_hub.scrapers.ebay import EbayScraper


def test_extract_item_id():
    assert EbayScraper._extract_item_id("https://www.ebay.com/itm/123456789") == "123456789"
    assert EbayScraper._extract_item_id("https://www.ebay.com/itm/123456789?hash=abc") == "123456789"
    assert EbayScraper._extract_item_id("https://www.ebay.com/other") is None


def test_scraper_init():
    scraper = EbayScraper(timeout=10.0, site="co.jp")
    assert scraper._base_url == "https://www.ebay.co.jp"
    assert scraper._timeout == 10.0


def test_parse_search_item_html():
    """検索結果HTMLの個別アイテムパースをテストする."""
    from bs4 import BeautifulSoup

    html = """
    <li class="s-item">
        <div class="s-item__title">
            <span role="heading">Test Product Title</span>
        </div>
        <a class="s-item__link" href="https://www.ebay.com/itm/999888777">link</a>
        <span class="s-item__price">$49.99</span>
        <span class="s-item__shipping">Free shipping</span>
        <span class="SECONDARY_INFO">Brand New</span>
    </li>
    """
    soup = BeautifulSoup(html, "lxml")
    item = soup.select_one("li.s-item")
    scraper = EbayScraper()
    product = scraper._parse_search_item(item)

    assert product is not None
    assert product.item_id == "999888777"
    assert product.title == "Test Product Title"
    assert product.price == 49.99
    assert product.shipping.free_shipping is True
    assert product.condition == ListingCondition.NEW


def test_parse_search_item_used():
    from bs4 import BeautifulSoup

    html = """
    <li class="s-item">
        <div class="s-item__title">
            <span role="heading">Used Item</span>
        </div>
        <a class="s-item__link" href="https://www.ebay.com/itm/111222333">link</a>
        <span class="s-item__price">$10.00</span>
        <span class="s-item__shipping">+$5.99 shipping</span>
        <span class="SECONDARY_INFO">Pre-Owned</span>
    </li>
    """
    soup = BeautifulSoup(html, "lxml")
    item = soup.select_one("li.s-item")
    scraper = EbayScraper()
    product = scraper._parse_search_item(item)

    assert product is not None
    assert product.condition == ListingCondition.USED
    assert product.shipping.cost == 5.99
    assert product.shipping.free_shipping is False
