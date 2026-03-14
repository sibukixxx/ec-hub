"""eBay API クライアントのテスト."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from ec_hub.services.ebay_api import EBAY_API_PRODUCTION, EBAY_API_SANDBOX, EbayApiClient

# --- Fixtures ---


@pytest.fixture
def unconfigured_client():
    return EbayApiClient(app_id="", cert_id="", dev_id="", user_token="")


@pytest.fixture
def configured_client():
    return EbayApiClient(
        app_id="test_app",
        cert_id="test_cert",
        dev_id="test_dev",
        user_token="test_token",
    )


@pytest.fixture
def mock_http_client():
    mock = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}
    mock_response.raise_for_status = MagicMock()
    mock.put = AsyncMock(return_value=mock_response)
    mock.post = AsyncMock(return_value=mock_response)
    mock.get = AsyncMock(return_value=mock_response)
    mock.is_closed = False
    mock.aclose = AsyncMock()
    return mock, mock_response


# --- Existing tests (1-4) ---


def test_ebay_api_not_configured():
    client = EbayApiClient(app_id="", cert_id="", dev_id="", user_token="")
    assert client.is_configured is False


def test_ebay_api_configured():
    client = EbayApiClient(
        app_id="test_app",
        cert_id="test_cert",
        dev_id="test_dev",
        user_token="test_token",
    )
    assert client.is_configured is True


def test_ebay_api_sandbox_url():
    client = EbayApiClient(
        app_id="test",
        cert_id="test",
        dev_id="test",
        user_token="test",
        sandbox=True,
    )
    assert client._base_url == EBAY_API_SANDBOX


def test_ebay_api_production_url():
    client = EbayApiClient(
        app_id="test",
        cert_id="test",
        dev_id="test",
        user_token="test",
        sandbox=False,
    )
    assert client._base_url == EBAY_API_PRODUCTION


# --- Not configured tests (5-11) ---


@pytest.mark.asyncio
async def test_create_inventory_item_not_configured(unconfigured_client):
    """should raise RuntimeError when credentials are not configured."""
    with pytest.raises(RuntimeError, match="eBay API credentials not configured"):
        await unconfigured_client.create_or_replace_inventory_item(
            "SKU-001",
            title="Test",
            description="Test desc",
            price_usd=29.99,
        )


@pytest.mark.asyncio
async def test_create_offer_not_configured(unconfigured_client):
    """should raise RuntimeError when credentials are not configured."""
    with pytest.raises(RuntimeError, match="eBay API credentials not configured"):
        await unconfigured_client.create_offer(
            "SKU-001",
            price_usd=29.99,
            category_id="12345",
            listing_description="Test listing",
        )


@pytest.mark.asyncio
async def test_publish_offer_not_configured(unconfigured_client):
    """should raise RuntimeError when credentials are not configured."""
    with pytest.raises(RuntimeError, match="eBay API credentials not configured"):
        await unconfigured_client.publish_offer("OFFER-001")


@pytest.mark.asyncio
async def test_get_orders_not_configured(unconfigured_client):
    """should raise RuntimeError when credentials are not configured."""
    with pytest.raises(RuntimeError, match="eBay API credentials not configured"):
        await unconfigured_client.get_orders()


@pytest.mark.asyncio
async def test_get_order_not_configured(unconfigured_client):
    """should raise RuntimeError when credentials are not configured."""
    with pytest.raises(RuntimeError, match="eBay API credentials not configured"):
        await unconfigured_client.get_order("ORDER-001")


@pytest.mark.asyncio
async def test_create_shipping_fulfillment_not_configured(unconfigured_client):
    """should raise RuntimeError when credentials are not configured."""
    with pytest.raises(RuntimeError, match="eBay API credentials not configured"):
        await unconfigured_client.create_shipping_fulfillment(
            "ORDER-001",
            tracking_number="TRACK-123",
        )


@pytest.mark.asyncio
async def test_get_selling_limit_not_configured(unconfigured_client):
    """should raise RuntimeError when credentials are not configured."""
    with pytest.raises(RuntimeError, match="eBay API credentials not configured"):
        await unconfigured_client.get_selling_limit()


# --- Success tests (12-19) ---


@pytest.mark.asyncio
async def test_create_inventory_item_success(configured_client, mock_http_client):
    """should call PUT with correct SKU path and return sku with status."""
    mock_client, mock_response = mock_http_client
    mock_response.status_code = 204
    configured_client._client = mock_client

    result = await configured_client.create_or_replace_inventory_item(
        "SKU-001",
        title="Test Item",
        description="Test description",
        price_usd=29.99,
    )

    assert result["sku"] == "SKU-001"
    assert result["status"] == 204
    mock_client.put.assert_called_once()
    call_args = mock_client.put.call_args
    assert call_args[0][0] == "/sell/inventory/v1/inventory_item/SKU-001"
    payload = call_args[1]["json"]
    assert payload["product"]["title"] == "Test Item"
    assert payload["product"]["description"] == "Test description"
    assert payload["condition"] == "NEW"
    assert payload["availability"]["shipToLocationAvailability"]["quantity"] == 1


@pytest.mark.asyncio
async def test_create_offer_success(configured_client, mock_http_client):
    """should call POST with correct offer payload and return response data."""
    mock_client, mock_response = mock_http_client
    mock_response.json.return_value = {"offerId": "OFFER-123"}
    configured_client._client = mock_client

    result = await configured_client.create_offer(
        "SKU-001",
        price_usd=49.99,
        category_id="12345",
        listing_description="Great product",
        fulfillment_policy_id="FP-001",
        payment_policy_id="PP-001",
        return_policy_id="RP-001",
    )

    assert result["offerId"] == "OFFER-123"
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "/sell/inventory/v1/offer"
    payload = call_args[1]["json"]
    assert payload["sku"] == "SKU-001"
    assert payload["marketplaceId"] == "EBAY_US"
    assert payload["format"] == "FIXED_PRICE"
    assert payload["pricingSummary"]["price"]["value"] == "49.99"
    assert payload["pricingSummary"]["price"]["currency"] == "USD"
    assert payload["categoryId"] == "12345"
    assert payload["listingDescription"] == "Great product"
    assert payload["listingPolicies"]["fulfillmentPolicyId"] == "FP-001"
    assert payload["listingPolicies"]["paymentPolicyId"] == "PP-001"
    assert payload["listingPolicies"]["returnPolicyId"] == "RP-001"


@pytest.mark.asyncio
async def test_publish_offer_success(configured_client, mock_http_client):
    """should call POST to publish endpoint and return response data."""
    mock_client, mock_response = mock_http_client
    mock_response.json.return_value = {"listingId": "LISTING-789"}
    configured_client._client = mock_client

    result = await configured_client.publish_offer("OFFER-123")

    assert result["listingId"] == "LISTING-789"
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "/sell/inventory/v1/offer/OFFER-123/publish"


@pytest.mark.asyncio
async def test_get_orders_success(configured_client, mock_http_client):
    """should call GET with correct limit and offset params."""
    mock_client, mock_response = mock_http_client
    mock_response.json.return_value = {
        "orders": [{"orderId": "ORDER-001"}],
        "total": 1,
    }
    configured_client._client = mock_client

    result = await configured_client.get_orders(limit=10, offset=5)

    assert result["total"] == 1
    assert result["orders"][0]["orderId"] == "ORDER-001"
    mock_client.get.assert_called_once()
    call_args = mock_client.get.call_args
    assert call_args[0][0] == "/sell/fulfillment/v1/order"
    params = call_args[1]["params"]
    assert params["limit"] == "10"
    assert params["offset"] == "5"
    assert "filter" not in params


@pytest.mark.asyncio
async def test_get_orders_with_status_filter(configured_client, mock_http_client):
    """should include filter param when order_fulfillment_status is specified."""
    mock_client, mock_response = mock_http_client
    mock_response.json.return_value = {"orders": [], "total": 0}
    configured_client._client = mock_client

    await configured_client.get_orders(order_fulfillment_status="NOT_STARTED")

    call_args = mock_client.get.call_args
    params = call_args[1]["params"]
    assert params["filter"] == "orderfulfillmentstatus:{NOT_STARTED}"


@pytest.mark.asyncio
async def test_get_order_success(configured_client, mock_http_client):
    """should call GET with correct order ID path."""
    mock_client, mock_response = mock_http_client
    mock_response.json.return_value = {
        "orderId": "ORDER-001",
        "orderFulfillmentStatus": "FULFILLED",
    }
    configured_client._client = mock_client

    result = await configured_client.get_order("ORDER-001")

    assert result["orderId"] == "ORDER-001"
    assert result["orderFulfillmentStatus"] == "FULFILLED"
    mock_client.get.assert_called_once()
    call_args = mock_client.get.call_args
    assert call_args[0][0] == "/sell/fulfillment/v1/order/ORDER-001"


@pytest.mark.asyncio
async def test_create_shipping_fulfillment_success(configured_client, mock_http_client):
    """should call POST with tracking number and carrier in payload."""
    mock_client, mock_response = mock_http_client
    mock_response.json.return_value = {"fulfillmentId": "FULFILL-001"}
    configured_client._client = mock_client

    line_items = [{"lineItemId": "LI-001", "quantity": 1}]
    result = await configured_client.create_shipping_fulfillment(
        "ORDER-001",
        tracking_number="JP123456789",
        shipping_carrier="JP_POST",
        line_items=line_items,
    )

    assert result["fulfillmentId"] == "FULFILL-001"
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "/sell/fulfillment/v1/order/ORDER-001/shipping_fulfillment"
    payload = call_args[1]["json"]
    assert payload["trackingNumber"] == "JP123456789"
    assert payload["shippingCarrierCode"] == "JP_POST"
    assert "shippedDate" in payload
    assert payload["lineItems"] == line_items


@pytest.mark.asyncio
async def test_get_selling_limit_success(configured_client, mock_http_client):
    """should parse sellingLimit from privilege response."""
    mock_client, mock_response = mock_http_client
    mock_response.json.return_value = {
        "sellingLimit": {
            "amount": {"value": "25000.00", "currency": "USD"},
            "quantity": 250,
        },
    }
    configured_client._client = mock_client

    result = await configured_client.get_selling_limit()

    assert result["amount_limit"] == "25000.00"
    assert result["quantity_limit"] == 250
    mock_client.get.assert_called_once()
    call_args = mock_client.get.call_args
    assert call_args[0][0] == "/sell/account/v1/privilege"


# --- Client lifecycle tests (20-21) ---


@pytest.mark.asyncio
async def test_close_client(configured_client, mock_http_client):
    """should call aclose on the underlying httpx client."""
    mock_client, _ = mock_http_client
    configured_client._client = mock_client

    await configured_client.close()

    mock_client.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_close_client_when_already_closed(configured_client, mock_http_client):
    """should not call aclose when client is already closed."""
    mock_client, _ = mock_http_client
    mock_client.is_closed = True
    configured_client._client = mock_client

    await configured_client.close()

    mock_client.aclose.assert_not_called()


@pytest.mark.asyncio
async def test_context_manager(configured_client, mock_http_client):
    """should support async with and call close on exit."""
    mock_client, _ = mock_http_client
    configured_client._client = mock_client

    async with configured_client as client:
        assert client is configured_client

    mock_client.aclose.assert_called_once()
