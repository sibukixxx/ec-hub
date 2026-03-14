"""Order Manager モジュールのテスト."""

from unittest.mock import AsyncMock

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


async def test_register_order_with_listing_id(order_manager, db):
    """listing_idを指定して注文登録できる."""
    cid = await db.add_candidate(
        item_code="B09TRACE",
        source_site="amazon",
        title_jp="トレース商品",
        title_en="Trace Product",
        cost_jpy=3000,
        ebay_price_usd=80.0,
        net_profit_jpy=5000,
        margin_rate=1.67,
    )
    lid = await db.add_listing(
        candidate_id=cid,
        sku=f"ECHUB-{cid}",
        title_en="Trace Product",
        listed_price_usd=80.0,
        listed_fx_rate=150.0,
    )
    oid = await order_manager.register_order(
        ebay_order_id="TRACE-001",
        buyer_username="trace_buyer",
        sale_price_usd=80.0,
        destination_country="US",
        candidate_id=cid,
        listing_id=lid,
    )
    order = await db.get_order_by_id(oid)
    assert order["listing_id"] == lid
    assert order["candidate_id"] == cid


async def test_resolve_listing_from_sku(order_manager, db):
    """SKUからlisting/candidateを逆引きできる."""
    cid = await db.add_candidate(
        item_code="B09RESOLVE",
        source_site="amazon",
        title_jp="逆引き商品",
        title_en="Resolve Product",
        cost_jpy=4000,
        ebay_price_usd=100.0,
        net_profit_jpy=7000,
        margin_rate=1.75,
    )
    await db.add_listing(
        candidate_id=cid,
        sku=f"ECHUB-{cid}",
        title_en="Resolve Product",
        listed_price_usd=100.0,
        listed_fx_rate=150.0,
    )

    listing = await db.get_listing_by_sku(f"ECHUB-{cid}")
    assert listing is not None
    assert listing["candidate_id"] == cid

    candidate = await db.get_candidate_by_id(listing["candidate_id"])
    assert candidate is not None
    assert candidate["item_code"] == "B09RESOLVE"


async def test_register_order_updates_listing_status_to_sold(order_manager, db):
    """注文登録時にlisting statusがsoldに更新される."""
    cid = await db.add_candidate(
        item_code="B09SOLD",
        source_site="amazon",
        title_jp="売約済み商品",
        title_en="Sold Product",
        cost_jpy=3000,
        ebay_price_usd=80.0,
        net_profit_jpy=5000,
        margin_rate=1.67,
    )
    lid = await db.add_listing(
        candidate_id=cid,
        sku=f"ECHUB-{cid}",
        title_en="Sold Product",
        listed_price_usd=80.0,
        listed_fx_rate=150.0,
    )
    listing_before = await db.get_listing_by_id(lid)
    assert listing_before["status"] == "active"

    await order_manager.register_order(
        ebay_order_id="SOLD-001",
        buyer_username="buyer_sold",
        sale_price_usd=80.0,
        destination_country="US",
        candidate_id=cid,
        listing_id=lid,
    )
    listing_after = await db.get_listing_by_id(lid)
    assert listing_after["status"] == "sold"


async def test_register_order_without_listing_does_not_fail(order_manager, db):
    """listing_idなしの注文登録でもエラーにならない."""
    oid = await order_manager.register_order(
        ebay_order_id="NO-LID-001",
        buyer_username="buyer_nolid",
        sale_price_usd=50.0,
        destination_country="US",
    )
    order = await db.get_order_by_id(oid)
    assert order["listing_id"] is None


async def test_resolve_listing_from_order_line_items(order_manager, db):
    """eBay注文のline itemsからSKU→listing→candidateを逆引きする."""
    cid = await db.add_candidate(
        item_code="B09LINE",
        source_site="amazon",
        title_jp="ラインアイテム商品",
        title_en="Line Item Product",
        cost_jpy=4000,
        ebay_price_usd=100.0,
        net_profit_jpy=7000,
        margin_rate=1.75,
    )
    lid = await db.add_listing(
        candidate_id=cid,
        sku=f"ECHUB-{cid}",
        title_en="Line Item Product",
        listed_price_usd=100.0,
        listed_fx_rate=150.0,
    )

    resolved = await order_manager.resolve_listing_from_line_items(
        [
            {"sku": f"ECHUB-{cid}", "lineItemId": "LI-001"},
        ]
    )
    assert resolved is not None
    assert resolved["listing_id"] == lid
    assert resolved["candidate_id"] == cid


async def test_resolve_listing_returns_none_for_unknown_sku(order_manager, db):
    """未知のSKUではNoneを返す."""
    resolved = await order_manager.resolve_listing_from_line_items(
        [
            {"sku": "UNKNOWN-SKU", "lineItemId": "LI-999"},
        ]
    )
    assert resolved is None


async def test_cancel_order_restores_listing_to_active(order_manager, db):
    """注文キャンセル時にlisting statusがactiveに戻る."""
    cid = await db.add_candidate(
        item_code="B09CANCEL",
        source_site="amazon",
        title_jp="キャンセル商品",
        title_en="Cancel Product",
        cost_jpy=3000,
        ebay_price_usd=80.0,
        net_profit_jpy=5000,
        margin_rate=1.67,
    )
    lid = await db.add_listing(
        candidate_id=cid,
        sku=f"ECHUB-{cid}",
        title_en="Cancel Product",
        listed_price_usd=80.0,
        listed_fx_rate=150.0,
    )
    oid = await order_manager.register_order(
        ebay_order_id="CANCEL-001",
        buyer_username="buyer_cancel",
        sale_price_usd=80.0,
        destination_country="US",
        candidate_id=cid,
        listing_id=lid,
    )
    # listing should be sold
    listing = await db.get_listing_by_id(lid)
    assert listing["status"] == "sold"

    # cancel the order
    await order_manager.cancel_order(oid)

    # listing should be active again
    listing = await db.get_listing_by_id(lid)
    assert listing["status"] == "active"

    # order should be cancelled
    order = await db.get_order_by_id(oid)
    assert order["status"] == "cancelled"


async def test_cancel_order_without_listing(order_manager, db):
    """listing_idなしの注文キャンセルでもエラーにならない."""
    oid = await order_manager.register_order(
        ebay_order_id="CANCEL-002",
        buyer_username="buyer_cancel2",
        sale_price_usd=50.0,
        destination_country="US",
    )
    await order_manager.cancel_order(oid)
    order = await db.get_order_by_id(oid)
    assert order["status"] == "cancelled"


async def test_check_new_orders_resolves_traceability_from_line_items(order_manager, db):
    cid = await db.add_candidate(
        item_code="B09ORDERTRACE",
        source_site="amazon",
        title_jp="注文トレース商品",
        title_en="Order Trace Product",
        cost_jpy=5000,
        ebay_price_usd=120.0,
        net_profit_jpy=7000,
        margin_rate=1.4,
    )
    lid = await db.add_listing(
        candidate_id=cid,
        sku=f"ECHUB-{cid}",
        title_en="Order Trace Product",
        listed_price_usd=120.0,
        listed_fx_rate=150.0,
        listing_id="EBAY-LIST-ORDER-1",
    )
    order_manager._ebay_api = AsyncMock()
    order_manager._ebay_api.is_configured = True
    order_manager._ebay_api.get_orders = AsyncMock(
        return_value={
            "orders": [
                {
                    "orderId": "ORDER-TRACE-001",
                    "buyer": {"username": "trace_buyer"},
                    "pricingSummary": {"total": {"value": "120.0"}},
                    "fulfillmentStartInstructions": [
                        {"shippingStep": {"shipTo": {"contactAddress": {"countryCode": "US"}}}},
                    ],
                    "lineItems": [
                        {"sku": f"ECHUB-{cid}", "listingId": "EBAY-LIST-ORDER-1"},
                    ],
                },
            ],
        }
    )

    orders = await order_manager.check_new_orders()
    assert len(orders) == 1
    assert orders[0]["listing_id"] == lid
    assert orders[0]["candidate_id"] == cid


async def test_register_order_marks_listing_sold(order_manager, db):
    cid = await db.add_candidate(
        item_code="B09SOLD",
        source_site="amazon",
        title_jp="販売済み商品",
        title_en="Sold Product",
        cost_jpy=3000,
        ebay_price_usd=80.0,
        net_profit_jpy=4000,
        margin_rate=1.33,
    )
    lid = await db.add_listing(
        candidate_id=cid,
        sku=f"ECHUB-{cid}",
        title_en="Sold Product",
        listed_price_usd=80.0,
        listed_fx_rate=150.0,
    )

    await order_manager.register_order(
        ebay_order_id="TRACE-SOLD-001",
        buyer_username="trace_buyer",
        sale_price_usd=80.0,
        destination_country="US",
        listing_id=lid,
    )

    listing = await db.get_listing_by_id(lid)
    candidate = await db.get_candidate_by_id(cid)
    assert listing["status"] == "sold"
    assert candidate["status"] == "listed"
