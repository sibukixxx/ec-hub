"""eBay API クライアントのテスト."""

from ec_hub.services.ebay_api import EBAY_API_PRODUCTION, EBAY_API_SANDBOX, EbayApiClient


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
        app_id="test", cert_id="test", dev_id="test",
        user_token="test", sandbox=True,
    )
    assert client._base_url == EBAY_API_SANDBOX


def test_ebay_api_production_url():
    client = EbayApiClient(
        app_id="test", cert_id="test", dev_id="test",
        user_token="test", sandbox=False,
    )
    assert client._base_url == EBAY_API_PRODUCTION
