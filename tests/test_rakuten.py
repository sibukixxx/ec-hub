"""楽天APIクライアントのテスト."""

from ec_hub.scrapers.rakuten import RakutenClient


def test_rakuten_not_configured():
    client = RakutenClient(app_id="")
    assert client.is_configured is False
    assert client.site_name == "rakuten"


def test_rakuten_configured():
    client = RakutenClient(app_id="test_app_id")
    assert client.is_configured is True


async def test_rakuten_search_unconfigured():
    client = RakutenClient(app_id="")
    result = await client.search("test query")
    assert result.source_site == "rakuten"
    assert result.query == "test query"
    assert len(result.products) == 0


async def test_rakuten_get_item_unconfigured():
    client = RakutenClient(app_id="")
    result = await client.get_item("shop:item123")
    assert result is None


def test_parse_item():
    item_data = {
        "itemName": "テスト商品 楽天",
        "itemPrice": 2980,
        "itemCode": "testshop:item-001",
        "itemUrl": "https://item.rakuten.co.jp/testshop/item-001/",
        "mediumImageUrls": [
            {"imageUrl": "https://thumbnail.image.rakuten.co.jp/test.jpg"},
        ],
        "genreName": "ホビー",
        "reviewCount": 42,
        "reviewAverage": "4.5",
        "availability": 1,
    }
    product = RakutenClient._parse_item(item_data)
    assert product is not None
    assert product.item_code == "testshop:item-001"
    assert product.source_site == "rakuten"
    assert product.title == "テスト商品 楽天"
    assert product.price_jpy == 2980
    assert product.category == "ホビー"
    assert product.review_count == 42
    assert product.rating == 4.5
    assert product.availability is True


def test_parse_item_string_images():
    """画像URLが文字列リストの場合のテスト."""
    item_data = {
        "itemName": "String Image Product",
        "itemPrice": 1000,
        "itemCode": "shop:item-002",
        "itemUrl": "https://item.rakuten.co.jp/shop/item-002/",
        "mediumImageUrls": ["https://example.com/img.jpg"],
    }
    product = RakutenClient._parse_item(item_data)
    assert product is not None
    assert product.image_url == "https://example.com/img.jpg"


def test_parse_item_no_price():
    item_data = {
        "itemName": "No Price",
        "itemPrice": 0,
        "itemCode": "shop:item-003",
    }
    product = RakutenClient._parse_item(item_data)
    assert product is None


def test_parse_item_no_title():
    item_data = {
        "itemName": "",
        "itemPrice": 1000,
    }
    product = RakutenClient._parse_item(item_data)
    assert product is None
