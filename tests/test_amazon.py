"""Amazon PA-API クライアントのテスト."""

from ec_hub.scrapers.amazon import AmazonClient


def test_amazon_not_configured():
    client = AmazonClient(access_key="", secret_key="", partner_tag="")
    assert client.is_configured is False
    assert client.site_name == "amazon"


def test_amazon_configured():
    client = AmazonClient(
        access_key="test_key",
        secret_key="test_secret",
        partner_tag="test_tag-22",
    )
    assert client.is_configured is True


async def test_amazon_search_unconfigured():
    client = AmazonClient(access_key="", secret_key="", partner_tag="")
    result = await client.search("test query")
    assert result.source_site == "amazon"
    assert result.query == "test query"
    assert len(result.products) == 0


async def test_amazon_get_item_unconfigured():
    client = AmazonClient(access_key="", secret_key="", partner_tag="")
    result = await client.get_item("B09TEST")
    assert result is None


def test_parse_item():
    item_data = {
        "ASIN": "B09TEST123",
        "DetailPageURL": "https://www.amazon.co.jp/dp/B09TEST123",
        "ItemInfo": {
            "Title": {"DisplayValue": "テスト商品 日本語タイトル"},
            "Classifications": {
                "Binding": {"DisplayValue": "おもちゃ"},
            },
        },
        "Offers": {
            "Listings": [
                {"Price": {"Amount": 3500.0, "Currency": "JPY"}},
            ],
        },
        "Images": {
            "Primary": {
                "Large": {"URL": "https://images-na.ssl-images-amazon.com/test.jpg"},
            },
        },
    }
    product = AmazonClient._parse_item(item_data)
    assert product is not None
    assert product.item_code == "B09TEST123"
    assert product.source_site == "amazon"
    assert product.title == "テスト商品 日本語タイトル"
    assert product.price_jpy == 3500
    assert product.category == "おもちゃ"
    assert product.image_url == "https://images-na.ssl-images-amazon.com/test.jpg"


def test_parse_item_no_price():
    item_data = {
        "ASIN": "B09NOPRICE",
        "ItemInfo": {"Title": {"DisplayValue": "No Price Product"}},
        "Offers": {"Listings": []},
    }
    product = AmazonClient._parse_item(item_data)
    assert product is None


def test_parse_item_no_asin():
    item_data = {"ItemInfo": {"Title": {"DisplayValue": "No ASIN"}}}
    product = AmazonClient._parse_item(item_data)
    assert product is None
