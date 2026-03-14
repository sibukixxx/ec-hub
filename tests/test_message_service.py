"""MessageService のテスト."""

import pytest

from ec_hub.context import AppContext
from ec_hub.db import Database
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
    db = Database(":memory:")
    await db.connect()
    ctx = AppContext(settings=test_settings, fee_rules=test_fee_rules, db=db)
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


async def test_handle_message_preserves_traceability_links(ctx):
    cid = await ctx.db.add_candidate(
        item_code="B09MSGTRACE",
        source_site="amazon",
        title_jp="メッセージ連携商品",
        title_en="Message Trace Product",
        cost_jpy=3000,
        ebay_price_usd=80.0,
        net_profit_jpy=5000,
        margin_rate=1.67,
    )
    lid = await ctx.db.add_listing(
        candidate_id=cid,
        sku=f"ECHUB-{cid}",
        title_en="Message Trace Product",
        listed_price_usd=80.0,
        listed_fx_rate=150.0,
    )
    oid = await ctx.db.add_order(
        ebay_order_id="ORD-MSG-SVC-001",
        listing_id=lid,
        sale_price_usd=80.0,
    )

    svc = MessageService(ctx)
    result = await svc.handle_message(
        buyer_username="buyer1",
        body="When will my item be shipped?",
        order_id=oid,
    )
    assert result is True

    messages = await ctx.db.get_messages(buyer_username="buyer1")
    assert len(messages) == 2
    for msg in messages:
        assert msg["order_id"] == oid
        assert msg["listing_id"] == lid
        assert msg["candidate_id"] == cid
