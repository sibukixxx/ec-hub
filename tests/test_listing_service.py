"""ListingService のテスト."""

import pytest

from ec_hub.context import AppContext
from ec_hub.db import Database
from ec_hub.services.listing_service import ListingService


@pytest.fixture
def test_settings():
    return {
        "exchange_rate": {"fallback_rate": 150.0},
        "database": {"path": ":memory:"},
        "line": {},
        "listing": {"max_daily_listings": 10},
    }


@pytest.fixture
def test_fee_rules():
    return {
        "ebay_fees": {"default_rate": 0.1325},
        "payoneer": {"rate": 0.02},
        "fx_buffer": {"rate": 0.03},
        "packing": {"default_cost": 200},
        "shipping": {
            "zones": {
                "US": [{"max_weight_g": 500, "cost": 1500}],
                "OTHER": [{"max_weight_g": 500, "cost": 2000}],
            },
            "destination_zones": {"US": "US"},
        },
    }


@pytest.fixture
async def ctx(test_settings, test_fee_rules):
    db = Database(":memory:")
    await db.connect()
    ctx = AppContext(settings=test_settings, fee_rules=test_fee_rules, db=db)
    yield ctx
    await ctx.close()


async def test_listing_service_creation(ctx):
    svc = ListingService(ctx)
    assert svc is not None


async def test_calc_listing_price(ctx):
    svc = ListingService(ctx)
    price = svc.calc_listing_price(cost_jpy=3000, weight_g=500, fx_rate=150.0)
    assert price > 0
    # Price should ensure at least 30% margin
    assert price >= 3000 * 1.30 / 150.0 / 0.8175
