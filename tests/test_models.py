"""モデルのテスト."""

from ec_hub.models import (
    ListingCondition,
    Product,
    SearchResult,
    SellerInfo,
    ShippingInfo,
)


def test_product_creation():
    product = Product(
        item_id="123456789",
        title="Test Product",
        price=29.99,
        url="https://www.ebay.com/itm/123456789",
    )
    assert product.item_id == "123456789"
    assert product.title == "Test Product"
    assert product.price == 29.99
    assert product.currency == "USD"
    assert product.condition == ListingCondition.NOT_SPECIFIED


def test_product_with_seller():
    seller = SellerInfo(name="test_seller", feedback_score=100, feedback_percent=99.5)
    product = Product(
        item_id="123",
        title="Test",
        url="https://www.ebay.com/itm/123",
        seller=seller,
    )
    assert product.seller is not None
    assert product.seller.name == "test_seller"
    assert product.seller.feedback_percent == 99.5


def test_shipping_info():
    shipping = ShippingInfo(free_shipping=True, cost=0.0)
    assert shipping.free_shipping is True
    assert shipping.cost == 0.0


def test_search_result():
    products = [
        Product(item_id=str(i), title=f"Product {i}", url=f"https://www.ebay.com/itm/{i}")
        for i in range(3)
    ]
    result = SearchResult(query="test query", total_results=100, products=products)
    assert result.query == "test query"
    assert result.total_results == 100
    assert len(result.products) == 3


def test_listing_condition_enum():
    assert ListingCondition.NEW.value == "New"
    assert ListingCondition.USED.value == "Used"
    assert ListingCondition.REFURBISHED.value == "Certified Refurbished"
