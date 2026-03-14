"""無印良品スクレイパーのテスト."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from ec_hub.scrapers.muji import MujiClient


@pytest.fixture
def client():
    return MujiClient(timeout=5.0, max_retries=2)


# --- site_name ---

def test_site_name(client):
    assert client.site_name == "muji"


# --- _extract_item_code ---

def test_extract_item_code_from_data_attr():
    """data-product-id属性から商品コードを抽出."""
    from bs4 import BeautifulSoup
    html = '<div data-product-id="4550344294956"><a href="/detail/123">test</a></div>'
    tag = BeautifulSoup(html, "lxml").select_one("div")
    assert MujiClient._extract_item_code(tag) == "4550344294956"


def test_extract_item_code_from_link():
    """リンクURLから商品コードを抽出."""
    from bs4 import BeautifulSoup
    html = '<div><a href="/jp/ja/store/cmdty/detail/4550344294956">test</a></div>'
    tag = BeautifulSoup(html, "lxml").select_one("div")
    assert MujiClient._extract_item_code(tag) == "4550344294956"


def test_extract_item_code_jan_code():
    """JANコードパターンから商品コードを抽出."""
    from bs4 import BeautifulSoup
    html = '<div><a href="/store/4550344294956">test</a></div>'
    tag = BeautifulSoup(html, "lxml").select_one("div")
    assert MujiClient._extract_item_code(tag) == "4550344294956"


def test_extract_item_code_not_found():
    """商品コードが見つからない場合."""
    from bs4 import BeautifulSoup
    html = '<div><a href="/store/abc">test</a></div>'
    tag = BeautifulSoup(html, "lxml").select_one("div")
    assert MujiClient._extract_item_code(tag) is None


# --- _parse_price ---

def test_parse_price_yen_sign():
    """¥マーク付き価格のパース."""
    from bs4 import BeautifulSoup
    html = '<div><span class="price">¥1,990</span></div>'
    tag = BeautifulSoup(html, "lxml").select_one("div")
    assert MujiClient._parse_price(tag) == 1990


def test_parse_price_en_sign():
    """￥マーク付き価格のパース."""
    from bs4 import BeautifulSoup
    html = '<div><span class="price">￥3,490</span></div>'
    tag = BeautifulSoup(html, "lxml").select_one("div")
    assert MujiClient._parse_price(tag) == 3490


def test_parse_price_with_tax():
    """税込み表記の価格."""
    from bs4 import BeautifulSoup
    html = '<div><span class="price">990円</span></div>'
    tag = BeautifulSoup(html, "lxml").select_one("div")
    assert MujiClient._parse_price(tag) == 990


def test_parse_price_data_attr():
    """data-price属性の価格."""
    from bs4 import BeautifulSoup
    html = '<div><span class="price" data-price="2990">dummy</span></div>'
    tag = BeautifulSoup(html, "lxml").select_one("div")
    assert MujiClient._parse_price(tag) == 2990


def test_parse_price_not_found():
    """価格が見つからない場合."""
    from bs4 import BeautifulSoup
    html = '<div><span class="description">No price here</span></div>'
    tag = BeautifulSoup(html, "lxml").select_one("div")
    assert MujiClient._parse_price(tag) is None


# --- _parse_image ---

def test_parse_image():
    """画像URLの抽出."""
    from bs4 import BeautifulSoup
    html = '<div><img src="https://www.muji.com/img/product.jpg" /></div>'
    tag = BeautifulSoup(html, "lxml").select_one("div")
    assert MujiClient._parse_image(tag) == "https://www.muji.com/img/product.jpg"


def test_parse_image_data_src():
    """data-src属性からの画像URL."""
    from bs4 import BeautifulSoup
    html = '<div><img data-src="https://www.muji.com/img/lazy.jpg" /></div>'
    tag = BeautifulSoup(html, "lxml").select_one("div")
    assert MujiClient._parse_image(tag) == "https://www.muji.com/img/lazy.jpg"


def test_parse_image_not_found():
    """画像が見つからない場合."""
    from bs4 import BeautifulSoup
    html = '<div><span>No image</span></div>'
    tag = BeautifulSoup(html, "lxml").select_one("div")
    assert MujiClient._parse_image(tag) is None


# --- _parse_search_item ---

def _make_search_item_html(
    title="無印良品 化粧水",
    price="¥1,990",
    item_code="4550344294956",
    url="/jp/ja/store/cmdty/detail/4550344294956",
    image="https://www.muji.com/img/test.jpg",
):
    return f"""
    <li class="product-tile" data-product-id="{item_code}">
        <a href="{url}">
            <img src="{image}" />
            <h3>{title}</h3>
        </a>
        <span class="price">{price}</span>
    </li>
    """


def test_parse_search_item_basic(client):
    """基本的な検索結果アイテムのパース."""
    from bs4 import BeautifulSoup
    html = _make_search_item_html()
    tag = BeautifulSoup(html, "lxml").select_one("li")
    product = client._parse_search_item(tag)
    assert product is not None
    assert product.title == "無印良品 化粧水"
    assert product.price_jpy == 1990
    assert product.item_code == "4550344294956"
    assert product.source_site == "muji"


def test_parse_search_item_no_title(client):
    """タイトルがない場合."""
    from bs4 import BeautifulSoup
    html = '<li class="product-tile" data-product-id="123"><span class="price">¥990</span></li>'
    tag = BeautifulSoup(html, "lxml").select_one("li")
    product = client._parse_search_item(tag)
    assert product is None


def test_parse_search_item_no_price(client):
    """価格がない場合."""
    from bs4 import BeautifulSoup
    html = '<li class="product-tile" data-product-id="123"><h3>Test</h3></li>'
    tag = BeautifulSoup(html, "lxml").select_one("li")
    product = client._parse_search_item(tag)
    assert product is None


# --- _parse_search_results ---

def test_parse_search_results(client):
    """検索結果リストのパース."""
    html = f"""
    <html><body>
    <ul>
        {_make_search_item_html(title="商品A", item_code="111", price="¥990")}
        {_make_search_item_html(title="商品B", item_code="222", price="¥1,990")}
    </ul>
    </body></html>
    """
    products = client._parse_search_results(html)
    assert len(products) == 2
    assert products[0].title == "商品A"
    assert products[1].price_jpy == 1990


def test_parse_search_results_empty(client):
    """検索結果が空の場合."""
    html = "<html><body><p>見つかりませんでした</p></body></html>"
    products = client._parse_search_results(html)
    assert len(products) == 0


# --- _parse_item_page ---

def test_parse_item_page(client):
    """商品詳細ページのパース."""
    html = """
    <html><body>
    <h1>無印良品 敏感肌用 化粧水 高保湿タイプ</h1>
    <span class="price">¥1,990</span>
    <img src="https://www.muji.com/img/detail.jpg" />
    <nav class="breadcrumb">
        <li>ホーム</li><li>スキンケア</li><li>化粧水</li>
    </nav>
    </body></html>
    """
    product = client._parse_item_page(html, "4550344294956", "https://www.muji.com/jp/ja/store/cmdty/detail/4550344294956")
    assert product is not None
    assert product.title == "無印良品 敏感肌用 化粧水 高保湿タイプ"
    assert product.price_jpy == 1990
    assert product.item_code == "4550344294956"
    assert product.source_site == "muji"
    assert product.category == "スキンケア"


def test_parse_item_page_out_of_stock(client):
    """在庫切れの場合."""
    html = """
    <html><body>
    <h1>テスト商品</h1>
    <span class="price">¥990</span>
    <div class="out-of-stock">在庫切れ</div>
    </body></html>
    """
    product = client._parse_item_page(html, "123", "https://www.muji.com/123")
    assert product is not None
    assert product.availability is False


def test_parse_item_page_no_title(client):
    """タイトルがない場合."""
    html = '<html><body><span class="price">¥990</span></body></html>'
    product = client._parse_item_page(html, "123", "https://www.muji.com/123")
    assert product is None


def test_parse_item_page_no_price(client):
    """価格がない場合."""
    html = "<html><body><h1>テスト</h1></body></html>"
    product = client._parse_item_page(html, "123", "https://www.muji.com/123")
    assert product is None


# --- search (integration with mock) ---

async def test_search_success(client):
    """検索の成功ケース."""
    search_html = f"""
    <html><body>
    <ul>{_make_search_item_html()}</ul>
    </body></html>
    """
    mock_resp = AsyncMock()
    mock_resp.text = search_html
    mock_resp.raise_for_status = lambda: None

    with patch.object(client, "_get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_get.return_value = mock_client

        result = await client.search("化粧水")
        assert result.source_site == "muji"
        assert result.query == "化粧水"
        assert len(result.products) == 1


async def test_search_failure(client):
    """検索失敗時は空の結果."""
    with patch.object(client, "_fetch", side_effect=httpx.HTTPError("Network error")):
        result = await client.search("化粧水")
        assert result.source_site == "muji"
        assert len(result.products) == 0


# --- get_item (integration with mock) ---

async def test_get_item_success(client):
    """商品取得の成功ケース."""
    item_html = """
    <html><body>
    <h1>テスト商品</h1>
    <span class="price">¥2,990</span>
    </body></html>
    """
    with patch.object(client, "_fetch", return_value=item_html):
        product = await client.get_item("4550344294956")
        assert product is not None
        assert product.price_jpy == 2990


async def test_get_item_failure(client):
    """商品取得失敗時はNone."""
    with patch.object(client, "_fetch", side_effect=httpx.HTTPError("Not found")):
        product = await client.get_item("4550344294956")
        assert product is None


# --- close ---

async def test_close(client):
    """close()が正常に実行される."""
    await client.close()  # No client yet, should not raise


async def test_context_manager(client):
    """コンテキストマネージャーとして使用できる."""
    async with client:
        pass  # Should not raise
