"""OrderService のテスト."""

import pytest

from ec_hub.context import AppContext
from ec_hub.db import Database
from ec_hub.services.order_service import OrderService


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
    db = Database(":memory:")
    await db.connect()
    ctx = AppContext(settings=test_settings, fee_rules=test_fee_rules, db=db)
    yield ctx
    await ctx.close()


async def test_get_orders_empty(ctx):
    svc = OrderService(ctx)
    result = await svc.get_orders()
    assert result == []


async def test_get_orders_with_data(ctx):
    await ctx.db.add_order(
        ebay_order_id="OS-001", buyer_username="buyer1", sale_price_usd=80.0,
    )
    svc = OrderService(ctx)
    result = await svc.get_orders()
    assert len(result) == 1


async def test_get_order_by_id(ctx):
    oid = await ctx.db.add_order(
        ebay_order_id="OS-002", buyer_username="buyer2", sale_price_usd=50.0,
    )
    svc = OrderService(ctx)
    result = await svc.get_order(oid)
    assert result is not None
    assert result["ebay_order_id"] == "OS-002"


async def test_get_order_by_id_not_found(ctx):
    svc = OrderService(ctx)
    result = await svc.get_order(99999)
    assert result is None


async def test_get_orders_by_status(ctx):
    oid = await ctx.db.add_order(
        ebay_order_id="OS-003", sale_price_usd=60.0,
    )
    await ctx.db.update_order(oid, status="shipped")

    svc = OrderService(ctx)
    shipped = await svc.get_orders(status="shipped")
    assert len(shipped) == 1
    awaiting = await svc.get_orders(status="awaiting_purchase")
    assert len(awaiting) == 0
