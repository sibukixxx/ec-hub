"""利益計算のテスト."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from ec_hub.db import Database
from ec_hub.modules.profit_tracker import ProfitTracker


@pytest.fixture
def fee_rules():
    return {
        "ebay_fees": {"default_rate": 0.1325},
        "payoneer": {"rate": 0.02},
        "fx_buffer": {"rate": 0.03},
        "packing": {"default_cost": 200, "small": 100, "medium": 200, "large": 300},
        "shipping": {
            "zones": {
                "US": [
                    {"max_weight_g": 500, "cost": 1500},
                    {"max_weight_g": 1000, "cost": 2000},
                    {"max_weight_g": 2000, "cost": 2800},
                ],
                "OTHER": [
                    {"max_weight_g": 500, "cost": 2000},
                    {"max_weight_g": 1000, "cost": 2500},
                ],
            },
            "destination_zones": {"US": "US", "CA": "US", "GB": "EU"},
        },
    }


@pytest.fixture
def settings():
    return {
        "exchange_rate": {
            "base_url": "https://primary.example/latest/USD",
            "fallback_urls": ["https://fallback.example/latest/USD"],
            "fallback_rate": 150.0,
            "cache_ttl_minutes": 60,
        },
        "database": {"path": ":memory:"},
        "line": {},
    }


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.close()


@pytest.fixture
def tracker(db, settings, fee_rules):
    return ProfitTracker(db, settings, fee_rules)


def _mock_response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value=payload)
    return response


def _mock_httpx_client(*, get_side_effect=None):
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=get_side_effect)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


def test_calc_shipping(tracker):
    assert tracker.calc_shipping(300, "US") == 1500
    assert tracker.calc_shipping(800, "US") == 2000
    assert tracker.calc_shipping(1500, "US") == 2800


def test_calc_shipping_unknown_zone(tracker):
    # 未知の配送先はOTHERゾーンにフォールバック
    cost = tracker.calc_shipping(300, "ZZ")
    assert cost == 2000


def test_calc_net_profit_standard(tracker):
    """仕様書 §3.3 の「現実的（標準品）」ケース."""
    breakdown = tracker.calc_net_profit(
        jpy_cost=3000,
        ebay_price_usd=80.0,
        weight_g=500,
        destination="US",
        fx_rate=150.0,
    )
    # 売上: $80 * 150 = ¥12,000
    assert breakdown.jpy_revenue == 12000
    # eBay手数料: 12000 * 0.1325 = ¥1,590
    assert breakdown.ebay_fee == 1590
    # Payoneer手数料: 12000 * 0.02 = ¥240
    assert breakdown.payoneer_fee == 240
    # 送料: 500g, US = ¥1,500
    assert breakdown.shipping_cost == 1500
    # 梱包費: ¥200
    assert breakdown.packing_cost == 200
    # 為替バッファ: 12000 * 0.03 = ¥360
    assert breakdown.fx_buffer == 360
    # 費用合計: 3000 + 1590 + 240 + 1500 + 200 + 360 = ¥6,890
    assert breakdown.total_cost == 6890
    # 純利益: 12000 - 6890 = ¥5,110
    assert breakdown.net_profit == 5110
    # 利益率: 5110 / 3000 = 170.3%
    assert breakdown.margin_rate > 1.0


def test_calc_net_profit_heavy_item(tracker):
    """重量物ケース - 送料が高くなる."""
    breakdown = tracker.calc_net_profit(
        jpy_cost=3000,
        ebay_price_usd=80.0,
        weight_g=2000,
        destination="US",
        fx_rate=150.0,
    )
    assert breakdown.shipping_cost == 2800
    assert breakdown.net_profit < 5110  # 標準品より利益が少ない


def test_calc_net_profit_margin_too_low(tracker):
    """利益率が低いケース."""
    breakdown = tracker.calc_net_profit(
        jpy_cost=10000,
        ebay_price_usd=80.0,
        weight_g=500,
        destination="US",
        fx_rate=150.0,
    )
    # 仕入れが高いので利益率は低い
    assert breakdown.margin_rate < 0.30


async def test_get_fx_rate_fetches_from_fallback_api_and_persists_cache(db, settings, fee_rules):
    tracker = ProfitTracker(db, settings, fee_rules)
    tracker._notifier.notify_exchange_rate_warning = AsyncMock(return_value=True)
    mock_client = _mock_httpx_client(
        get_side_effect=[
            httpx.HTTPError("primary unavailable"),
            _mock_response({"conversion_rates": {"JPY": 161.25}}),
        ]
    )

    with patch("ec_hub.modules.profit_tracker.httpx.AsyncClient", return_value=mock_client):
        rate = await tracker.get_fx_rate()

    assert rate == 161.25
    cache = await db.get_exchange_rate_cache()
    assert cache is not None
    assert cache["rate"] == 161.25
    assert cache["source"] == "https://fallback.example/latest/USD"

    status = await db.get_integration_status("exchange_rate")
    assert status is not None
    assert status["status"] == "ok"
    assert status["error_message"] == "Fetched from https://fallback.example/latest/USD"
    tracker._notifier.notify_exchange_rate_warning.assert_not_awaited()


async def test_get_fx_rate_uses_fresh_db_cache_without_http(db, settings, fee_rules):
    await db.upsert_exchange_rate_cache(
        base_currency="USD",
        quote_currency="JPY",
        rate=158.4,
        source="https://cache.example/latest/USD",
        fetched_at=(datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
    )
    tracker = ProfitTracker(db, settings, fee_rules)
    tracker._notifier.notify_exchange_rate_warning = AsyncMock(return_value=True)

    with patch("ec_hub.modules.profit_tracker.httpx.AsyncClient") as client_cls:
        rate = await tracker.get_fx_rate()

    assert rate == 158.4
    client_cls.assert_not_called()

    status = await db.get_integration_status("exchange_rate")
    assert status is not None
    assert status["status"] == "ok"
    assert "Using cached rate 158.40" in status["error_message"]
    tracker._notifier.notify_exchange_rate_warning.assert_not_awaited()


async def test_get_fx_rate_uses_stale_db_cache_when_apis_fail(db, settings, fee_rules):
    await db.upsert_exchange_rate_cache(
        base_currency="USD",
        quote_currency="JPY",
        rate=152.3,
        source="https://cache.example/latest/USD",
        fetched_at=(datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(),
    )
    tracker = ProfitTracker(db, settings, fee_rules)
    tracker._notifier.notify_exchange_rate_warning = AsyncMock(return_value=True)
    mock_client = _mock_httpx_client(get_side_effect=httpx.HTTPError("all providers unavailable"))

    with patch("ec_hub.modules.profit_tracker.httpx.AsyncClient", return_value=mock_client):
        first_rate = await tracker.get_fx_rate()
        second_rate = await tracker.get_fx_rate()

    assert first_rate == 152.3
    assert second_rate == 152.3

    status = await db.get_integration_status("exchange_rate")
    assert status is not None
    assert status["status"] == "degraded"
    assert "Using last known rate 152.30" in status["error_message"]
    tracker._notifier.notify_exchange_rate_warning.assert_awaited_once()


async def test_get_fx_rate_uses_static_fallback_when_no_cache_exists(db, settings, fee_rules):
    tracker = ProfitTracker(db, settings, fee_rules)
    tracker._notifier.notify_exchange_rate_warning = AsyncMock(return_value=True)
    mock_client = _mock_httpx_client(get_side_effect=httpx.HTTPError("all providers unavailable"))

    with patch("ec_hub.modules.profit_tracker.httpx.AsyncClient", return_value=mock_client):
        first_rate = await tracker.get_fx_rate()
        second_rate = await tracker.get_fx_rate()

    assert first_rate == 150.0
    assert second_rate == 150.0

    status = await db.get_integration_status("exchange_rate")
    assert status is not None
    assert status["status"] == "degraded"
    assert "Using static fallback 150.00" in status["error_message"]
    tracker._notifier.notify_exchange_rate_warning.assert_awaited_once()
