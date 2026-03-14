"""MessageService のテスト."""

import pytest

from ec_hub.context import AppContext
from ec_hub.services.message_service import MessageService


@pytest.fixture
def test_settings():
    return {
        "exchange_rate": {"fallback_rate": 150.0},
        "database": {"path": ":memory:"},
        "line": {},
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
    ctx = await AppContext.create(
        settings=test_settings,
        fee_rules=test_fee_rules,
        db_path=":memory:",
    )
    yield ctx
    await ctx.close()


async def test_message_service_creation(ctx):
    svc = MessageService(ctx)
    assert svc is not None


async def test_handle_shipping_message(ctx):
    svc = MessageService(ctx)
    result = await svc.handle_message(
        buyer_username="buyer1",
        body="When will my item be shipped?",
    )
    # Shipping tracking messages should be auto-replied
    assert result is True
