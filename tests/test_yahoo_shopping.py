"""Yahoo!ショッピング APIクライアントのテスト."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from ec_hub.scrapers.yahoo_shopping import YahooShoppingClient


@pytest.fixture
def client():
    return YahooShoppingClient(app_id="test-app-id")


@pytest.fixture
def unconfigured_client():
    return YahooShoppingClient(app_id="")


def _mock_search_response(items: list[dict]) -> dict:
    return {"hits": items, "totalResultsAvailable": len(items)}


def _sample_item(**overrides) -> dict:
    base = {
        "name": "テスト商品 ワイヤレスイヤホン",
        "price": 3980,
        "code": "store1_item001",
        "url": "https://store.shopping.yahoo.co.jp/store1/item001.html",
        "image": {"small": "https://img.yahoo.co.jp/s.jpg", "medium": "https://img.yahoo.co.jp/m.jpg"},
        "inStock": True,
        "review": {"rate": "4.5", "count": 120},
        "genreCategory": {"id": 1234, "name": "オーディオ"},
    }
    base.update(overrides)
    return base


# --- site_name ---

def test_site_name(client):
    assert client.site_name == "yahoo_shopping"


# --- is_configured ---

def test_is_configured(client):
    assert client.is_configured is True


def test_is_not_configured(unconfigured_client):
    assert unconfigured_client.is_configured is False


# --- _parse_item ---

def test_parse_item_basic():
    item = _sample_item()
    product = YahooShoppingClient._parse_item(item)
    assert product is not None
    assert product.source_site == "yahoo_shopping"
    assert product.item_code == "store1_item001"
    assert product.title == "テスト商品 ワイヤレスイヤホン"
    assert product.price_jpy == 3980
    assert product.url == "https://store.shopping.yahoo.co.jp/store1/item001.html"
    assert product.image_url == "https://img.yahoo.co.jp/m.jpg"
    assert product.availability is True
    assert product.review_count == 120
    assert product.rating == 4.5
    assert product.category == "オーディオ"


def test_parse_item_no_name():
    product = YahooShoppingClient._parse_item({"name": "", "price": 1000})
    assert product is None


def test_parse_item_no_price():
    product = YahooShoppingClient._parse_item({"name": "test", "price": 0})
    assert product is None


def test_parse_item_no_price_field():
    product = YahooShoppingClient._parse_item({"name": "test"})
    assert product is None


def test_parse_item_out_of_stock():
    product = YahooShoppingClient._parse_item(_sample_item(inStock=False))
    assert product is not None
    assert product.availability is False


def test_parse_item_no_review():
    product = YahooShoppingClient._parse_item(_sample_item(review={}))
    assert product is not None
    assert product.review_count is None
    assert product.rating is None


def test_parse_item_no_image():
    product = YahooShoppingClient._parse_item(_sample_item(image={}))
    assert product is not None
    assert product.image_url is None


def test_parse_item_small_image_fallback():
    product = YahooShoppingClient._parse_item(_sample_item(image={"small": "https://img/s.jpg"}))
    assert product is not None
    assert product.image_url == "https://img/s.jpg"


def test_parse_item_no_genre():
    product = YahooShoppingClient._parse_item(_sample_item(genreCategory=None))
    assert product is not None
    assert product.category is None


def test_parse_item_invalid_rating():
    product = YahooShoppingClient._parse_item(_sample_item(review={"rate": "N/A", "count": 5}))
    assert product is not None
    assert product.rating is None
    assert product.review_count == 5


# --- search (async) ---

async def test_search_unconfigured(unconfigured_client):
    result = await unconfigured_client.search("test")
    assert result.source_site == "yahoo_shopping"
    assert result.products == []


async def test_search_success(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _mock_search_response([_sample_item(), _sample_item(name="商品2", price=5000)])
    mock_resp.raise_for_status = MagicMock()

    mock_http = AsyncMock(spec=httpx.AsyncClient)
    mock_http.get.return_value = mock_resp
    mock_http.is_closed = False
    client._client = mock_http
    client._last_request_time = 0

    result = await client.search("ワイヤレスイヤホン", max_results=10)
    assert result.source_site == "yahoo_shopping"
    assert len(result.products) == 2
    assert result.products[0].title == "テスト商品 ワイヤレスイヤホン"
    assert result.products[1].price_jpy == 5000

    call_params = mock_http.get.call_args.kwargs["params"]
    assert call_params["query"] == "ワイヤレスイヤホン"
    assert call_params["appid"] == "test-app-id"
    assert call_params["in_stock"] == "true"


async def test_search_api_error(client):
    mock_http = AsyncMock(spec=httpx.AsyncClient)
    mock_http.get.side_effect = httpx.HTTPStatusError("429", request=None, response=AsyncMock(status_code=429))
    mock_http.is_closed = False
    client._client = mock_http
    client._last_request_time = 0

    result = await client.search("test")
    assert result.products == []


async def test_search_max_results_capped(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = _mock_search_response([])
    mock_resp.raise_for_status = MagicMock()

    mock_http = AsyncMock(spec=httpx.AsyncClient)
    mock_http.get.return_value = mock_resp
    mock_http.is_closed = False
    client._client = mock_http
    client._last_request_time = 0

    await client.search("test", max_results=100)
    call_params = mock_http.get.call_args.kwargs["params"]
    assert call_params["results"] == 50  # Capped at API max


# --- get_item (async) ---

async def test_get_item_unconfigured(unconfigured_client):
    result = await unconfigured_client.get_item("item001")
    assert result is None


async def test_get_item_found(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = _mock_search_response([_sample_item(code="item001")])
    mock_resp.raise_for_status = MagicMock()

    mock_http = AsyncMock(spec=httpx.AsyncClient)
    mock_http.get.return_value = mock_resp
    mock_http.is_closed = False
    client._client = mock_http
    client._last_request_time = 0

    product = await client.get_item("item001")
    assert product is not None
    assert product.item_code == "item001"


async def test_get_item_not_found(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = _mock_search_response([])
    mock_resp.raise_for_status = MagicMock()

    mock_http = AsyncMock(spec=httpx.AsyncClient)
    mock_http.get.return_value = mock_resp
    mock_http.is_closed = False
    client._client = mock_http
    client._last_request_time = 0

    product = await client.get_item("nonexistent")
    assert product is None


# --- close ---

async def test_close(client):
    mock_http = AsyncMock(spec=httpx.AsyncClient)
    mock_http.is_closed = False
    client._client = mock_http
    await client.close()
    mock_http.aclose.assert_called_once()


async def test_close_already_closed(client):
    mock_http = AsyncMock(spec=httpx.AsyncClient)
    mock_http.is_closed = True
    client._client = mock_http
    await client.close()
    mock_http.aclose.assert_not_called()


async def test_close_no_client(client):
    client._client = None
    await client.close()  # Should not raise


# --- context manager ---

async def test_context_manager():
    async with YahooShoppingClient(app_id="test") as client:
        assert client.site_name == "yahoo_shopping"
