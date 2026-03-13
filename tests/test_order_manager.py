"""Order Manager モジュールのテスト."""

import pytest

from ec_hub.db import Database
from ec_hub.modules.order_manager import OrderManager


@pytest.fixture
def fee_rules():
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
def settings():
    return {
        "exchange_rate": {"fallback_rate": 150.0},
        "database": {"path": ":memory:"},
        "ebay": {},
        "line": {},
    }


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.close()


@pytest.fixture
def order_manager(db, settings, fee_rules):
    return OrderManager(db, settings, fee_rules)


async def test_register_order(order_manager, db):
    oid = await order_manager.register_order(
        ebay_order_id="12-34567-89012",
        buyer_username="test_buyer",
        sale_price_usd=80.0,
        destination_country="US",
    )
    assert oid is not None

    orders = await db.get_orders()
    assert len(orders) == 1
    assert orders[0]["ebay_order_id"] == "12-34567-89012"
    assert orders[0]["status"] == "awaiting_purchase"


async def test_mark_purchased(order_manager, db):
    oid = await order_manager.register_order(
        ebay_order_id="TEST-001",
        buyer_username="buyer1",
        sale_price_usd=50.0,
        destination_country="US",
    )
    await order_manager.mark_purchased(oid, actual_cost_jpy=3000)

    orders = await db.get_orders(status="purchased")
    assert len(orders) == 1
    assert orders[0]["actual_cost_jpy"] == 3000


async def test_mark_shipped(order_manager, db):
    oid = await order_manager.register_order(
        ebay_order_id="TEST-002",
        buyer_username="buyer2",
        sale_price_usd=60.0,
        destination_country="GB",
    )
    await order_manager.mark_purchased(oid, actual_cost_jpy=2500)
    await order_manager.mark_shipped(oid, "JP123456789", shipping_cost_jpy=2000)

    orders = await db.get_orders(status="shipped")
    assert len(orders) == 1
    assert orders[0]["tracking_number"] == "JP123456789"
    assert orders[0]["actual_shipping_jpy"] == 2000


async def test_complete_order(order_manager, db):
    oid = await order_manager.register_order(
        ebay_order_id="TEST-003",
        buyer_username="buyer3",
        sale_price_usd=80.0,
        destination_country="US",
    )
    await order_manager.mark_purchased(oid, actual_cost_jpy=3000)
    await order_manager.mark_shipped(oid, "JP999888777", shipping_cost_jpy=1500)
    await order_manager.mark_delivered(oid)
    await order_manager.complete_order(oid)

    orders = await db.get_orders(status="completed")
    assert len(orders) == 1
    assert orders[0]["net_profit_jpy"] is not None
    assert orders[0]["fx_rate"] is not None
    assert orders[0]["ebay_fee_jpy"] is not None


async def test_order_status_flow(order_manager, db):
    """注文ステータスの全フロー: awaiting → purchased → shipped → delivered → completed."""
    oid = await order_manager.register_order(
        ebay_order_id="FLOW-001",
        buyer_username="flow_buyer",
        sale_price_usd=100.0,
        destination_country="US",
    )

    orders = await db.get_orders(status="awaiting_purchase")
    assert len(orders) == 1

    await order_manager.mark_purchased(oid, 4000)
    orders = await db.get_orders(status="purchased")
    assert len(orders) == 1

    await order_manager.mark_shipped(oid, "JP111222333", 1800)
    orders = await db.get_orders(status="shipped")
    assert len(orders) == 1

    await order_manager.mark_delivered(oid)
    orders = await db.get_orders(status="delivered")
    assert len(orders) == 1

    await order_manager.complete_order(oid)
    orders = await db.get_orders(status="completed")
    assert len(orders) == 1
    assert orders[0]["net_profit_jpy"] is not None


async def test_check_new_orders_unconfigured(order_manager):
    """eBay API未設定時は空リスト."""
    result = await order_manager.check_new_orders()
    assert result == []
