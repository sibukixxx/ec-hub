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


def test_parse_search_item_no_title():
    """タイトル要素がない場合Noneを返す."""
    from bs4 import BeautifulSoup

    html = """
    <li class="s-item">
        <a class="s-item__link" href="https://www.ebay.com/itm/123">link</a>
        <span class="s-item__price">$10.00</span>
    </li>
    """
    soup = BeautifulSoup(html, "lxml")
    item = soup.select_one("li.s-item")
    scraper = EbayScraper()
    product = scraper._parse_search_item(item)
    assert product is None


def test_parse_search_item_shop_on_ebay():
    """'Shop on eBay'アイテムはスキップされる."""
    from bs4 import BeautifulSoup

    html = """
    <li class="s-item">
        <div class="s-item__title">
            <span role="heading">Shop on eBay</span>
        </div>
        <a class="s-item__link" href="https://www.ebay.com/itm/123456">link</a>
        <span class="s-item__price">$10.00</span>
    </li>
    """
    soup = BeautifulSoup(html, "lxml")
    item = soup.select_one("li.s-item")
    scraper = EbayScraper()
    product = scraper._parse_search_item(item)
    assert product is None


def test_parse_search_item_no_link():
    """アイテムリンクがない場合Noneを返す."""
    from bs4 import BeautifulSoup

    html = """
    <li class="s-item">
        <div class="s-item__title">
            <span role="heading">Valid Title</span>
        </div>
        <a class="s-item__link" href="https://www.ebay.com/other">link</a>
        <span class="s-item__price">$10.00</span>
    </li>
    """
    soup = BeautifulSoup(html, "lxml")
    item = soup.select_one("li.s-item")
    scraper = EbayScraper()
    product = scraper._parse_search_item(item)
    assert product is None


def test_parse_condition_open_box():
    """Open box状態を正しくパースする."""
    from bs4 import BeautifulSoup

    html = """
    <li class="s-item">
        <span class="SECONDARY_INFO">Open box</span>
    </li>
    """
    soup = BeautifulSoup(html, "lxml")
    item = soup.select_one("li.s-item")
    result = EbayScraper._parse_condition(item)
    assert result == ListingCondition.OPEN_BOX


def test_parse_condition_refurbished():
    """Refurbished状態を正しくパースする."""
    from bs4 import BeautifulSoup

    html = """
    <li class="s-item">
        <span class="SECONDARY_INFO">Certified - Refurbished</span>
    </li>
    """
    soup = BeautifulSoup(html, "lxml")
    item = soup.select_one("li.s-item")
    result = EbayScraper._parse_condition(item)
    assert result == ListingCondition.REFURBISHED


def test_parse_condition_for_parts():
    """For parts状態を正しくパースする."""
    from bs4 import BeautifulSoup

    html = """
    <li class="s-item">
        <span class="SECONDARY_INFO">For parts or not working</span>
    </li>
    """
    soup = BeautifulSoup(html, "lxml")
    item = soup.select_one("li.s-item")
    result = EbayScraper._parse_condition(item)
    assert result == ListingCondition.FOR_PARTS


def test_parse_condition_not_specified():
    """SECONDARY_INFO要素がない場合NOT_SPECIFIEDを返す."""
    from bs4 import BeautifulSoup

    html = """
    <li class="s-item">
        <span class="s-item__price">$10.00</span>
    </li>
    """
    soup = BeautifulSoup(html, "lxml")
    item = soup.select_one("li.s-item")
    result = EbayScraper._parse_condition(item)
    assert result == ListingCondition.NOT_SPECIFIED


def test_parse_search_results_count():
    """検索結果の件数パースを検証する."""
    scraper = EbayScraper()
    html = """
    <html><body>
    <h1 class="srp-controls__count-heading"><span class="BOLD">1,234</span> results</h1>
    <ul class="srp-results">
        <li class="s-item">
            <div class="s-item__title"><span role="heading">Product A</span></div>
            <a class="s-item__link" href="https://www.ebay.com/itm/100100100">link</a>
            <span class="s-item__price">$25.00</span>
        </li>
    </ul>
    </body></html>
    """
    result = scraper._parse_search_results(html, "test query", 1)
    assert result.total_results == 1234
    assert result.query == "test query"
    assert result.page == 1
    assert len(result.products) == 1
    assert result.products[0].item_id == "100100100"


def test_parse_search_results_empty():
    """空の検索結果を正しく処理する."""
    scraper = EbayScraper()
    html = """
    <html><body>
    <h1 class="srp-controls__count-heading"><span class="BOLD">0</span> results</h1>
    <ul class="srp-results"></ul>
    </body></html>
    """
    result = scraper._parse_search_results(html, "nonexistent", 1)
    assert result.total_results == 0
    assert result.products == []


def test_parse_item_page_basic():
    """商品詳細ページの基本パースを検証する."""
    scraper = EbayScraper()
    html = """
    <html>
    <h1 class="x-item-title__mainTitle"><span>Test Product</span></h1>
    <span itemprop="price">$49.99</span>
    <div class="x-sellercard-atf__info__about-seller"><a><span>test_seller</span></a></div>
    </html>
    """
    product = scraper._parse_item_page(html, "555666777", "https://www.ebay.com/itm/555666777")
    assert product is not None
    assert product.title == "Test Product"
    assert product.price == 49.99
    assert product.item_id == "555666777"
    assert product.seller is not None
    assert product.seller.name == "test_seller"
    assert product.url == "https://www.ebay.com/itm/555666777"


def test_parse_item_page_no_title():
    """タイトルがない商品詳細ページはNoneを返す."""
    scraper = EbayScraper()
    html = """
    <html>
    <span itemprop="price">$49.99</span>
    </html>
    """
    product = scraper._parse_item_page(html, "123", "https://www.ebay.com/itm/123")
    assert product is None


def test_parse_item_page_no_price():
    """価格がない場合price=Noneのプロダクトを返す."""
    scraper = EbayScraper()
    html = """
    <html>
    <h1 class="x-item-title__mainTitle"><span>No Price Product</span></h1>
    </html>
    """
    product = scraper._parse_item_page(html, "999", "https://www.ebay.com/itm/999")
    assert product is not None
    assert product.title == "No Price Product"
    assert product.price is None


def test_extract_item_id_query_param():
    """item=クエリパラメータ形式のID抽出を検証する."""
    assert EbayScraper._extract_item_id("https://www.ebay.com/sch?item=123456") == "123456"
    assert EbayScraper._extract_item_id("https://www.ebay.com/sch?foo=bar&item=789012&baz=1") == "789012"
