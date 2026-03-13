"""データベースのテスト."""

import pytest

from ec_hub.db import Database


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.close()


async def test_add_and_get_candidate(db):
    cid = await db.add_candidate(
        item_code="B09TEST",
        source_site="amazon",
        title_jp="テスト商品",
        title_en="Test Product",
        cost_jpy=3000,
        ebay_price_usd=80.0,
        net_profit_jpy=5110,
        margin_rate=1.70,
        weight_g=500,
    )
    assert cid is not None

    candidates = await db.get_candidates()
    assert len(candidates) == 1
    assert candidates[0]["item_code"] == "B09TEST"
    assert candidates[0]["title_jp"] == "テスト商品"
    assert candidates[0]["status"] == "pending"


async def test_update_candidate_status(db):
    cid = await db.add_candidate(
        item_code="B09TEST2",
        source_site="rakuten",
        title_jp="別のテスト商品",
        title_en=None,
        cost_jpy=5000,
        ebay_price_usd=120.0,
        net_profit_jpy=8000,
        margin_rate=1.60,
    )
    await db.update_candidate_status(cid, "approved")
    approved = await db.get_candidates(status="approved")
    assert len(approved) == 1
    assert approved[0]["id"] == cid


async def test_add_and_get_order(db):
    oid = await db.add_order(
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


async def test_update_order(db):
    oid = await db.add_order(
        ebay_order_id="99-99999-99999",
        sale_price_usd=50.0,
    )
    await db.update_order(oid, status="shipped", tracking_number="JP123456789")
    orders = await db.get_orders(status="shipped")
    assert len(orders) == 1
    assert orders[0]["tracking_number"] == "JP123456789"


async def test_add_message(db):
    mid = await db.add_message(
        buyer_username="buyer123",
        body="When will my item ship?",
        category="shipping_tracking",
    )
    assert mid is not None


async def test_save_daily_report(db):
    await db.save_daily_report(
        report_date="2026-03-13",
        total_revenue_jpy=50000,
        total_cost_jpy=20000,
        total_profit_jpy=30000,
        orders_count=3,
        new_candidates_count=10,
        new_listings_count=2,
    )
    # 同じ日付で上書き可能（INSERT OR REPLACE）
    await db.save_daily_report(
        report_date="2026-03-13",
        total_revenue_jpy=60000,
        total_cost_jpy=25000,
        total_profit_jpy=35000,
        orders_count=4,
        new_candidates_count=12,
        new_listings_count=3,
    )
