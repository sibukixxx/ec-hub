"""データベースのテスト."""

import os
from pathlib import Path

import pytest

from ec_hub.db import Database

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.close()


# --- Path resolution ---


class TestDatabasePathResolution:
    """Database path resolution tests."""

    def test_relative_path_resolves_to_absolute_from_project_root(self):
        database = Database("db/ebay.db")
        expected = _PROJECT_ROOT / "db" / "ebay.db"
        assert database._db_path == expected
        assert database._db_path.is_absolute()

    def test_absolute_path_is_used_as_is(self, tmp_path):
        abs_path = tmp_path / "test.db"
        database = Database(abs_path)
        assert database._db_path == abs_path

    def test_memory_path_is_preserved(self):
        database = Database(":memory:")
        assert database._db_path == Path(":memory:")

    async def test_connect_raises_when_parent_not_writable(self, tmp_path):
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        db_path = readonly_dir / "test.db"
        os.chmod(readonly_dir, 0o444)
        try:
            database = Database(db_path)
            with pytest.raises(PermissionError, match="write"):
                await database.connect()
        finally:
            os.chmod(readonly_dir, 0o755)


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


# --- get_candidate_by_id ---


async def test_get_candidate_by_id_returns_candidate_when_exists(db):
    cid = await db.add_candidate(
        item_code="B09BYID",
        source_site="amazon",
        title_jp="ID取得テスト商品",
        title_en="Test Product By ID",
        cost_jpy=3000,
        ebay_price_usd=80.0,
        net_profit_jpy=5000,
        margin_rate=1.67,
    )
    result = await db.get_candidate_by_id(cid)
    assert result is not None
    assert result["id"] == cid
    assert result["item_code"] == "B09BYID"
    assert result["title_jp"] == "ID取得テスト商品"


async def test_get_candidate_by_id_returns_none_when_not_exists(db):
    result = await db.get_candidate_by_id(99999)
    assert result is None


# --- get_order_by_id ---


async def test_get_order_by_id_returns_order_when_exists(db):
    oid = await db.add_order(
        ebay_order_id="BY-ID-001",
        buyer_username="buyer_by_id",
        sale_price_usd=120.0,
        destination_country="US",
    )
    result = await db.get_order_by_id(oid)
    assert result is not None
    assert result["id"] == oid
    assert result["ebay_order_id"] == "BY-ID-001"
    assert result["buyer_username"] == "buyer_by_id"


async def test_get_order_by_id_returns_none_when_not_exists(db):
    result = await db.get_order_by_id(99999)
    assert result is None


# --- count_candidates_by_status ---


async def test_count_candidates_by_status_returns_counts(db):
    await db.add_candidate(
        item_code="C1", source_site="amazon", title_jp="a", title_en=None,
        cost_jpy=1000, ebay_price_usd=30.0, net_profit_jpy=500, margin_rate=0.5,
    )
    await db.add_candidate(
        item_code="C2", source_site="amazon", title_jp="b", title_en=None,
        cost_jpy=2000, ebay_price_usd=60.0, net_profit_jpy=1000, margin_rate=0.5,
    )
    cid3 = await db.add_candidate(
        item_code="C3", source_site="rakuten", title_jp="c", title_en=None,
        cost_jpy=3000, ebay_price_usd=90.0, net_profit_jpy=1500, margin_rate=0.5,
    )
    await db.update_candidate_status(cid3, "approved")

    counts = await db.count_candidates_by_status()
    assert counts["pending"] == 2
    assert counts["approved"] == 1
    assert counts.get("rejected", 0) == 0


# --- count_orders_by_status ---


async def test_count_orders_by_status_returns_counts(db):
    oid1 = await db.add_order(
        ebay_order_id="CNT-001", sale_price_usd=50.0,
    )
    await db.add_order(
        ebay_order_id="CNT-002", sale_price_usd=60.0,
    )
    await db.update_order(oid1, status="completed", net_profit_jpy=3000)

    counts = await db.count_orders_by_status()
    assert counts["awaiting_purchase"] == 1
    assert counts["completed"] == 1


# --- get_total_completed_profit ---


async def test_get_total_completed_profit_returns_sum(db):
    oid1 = await db.add_order(ebay_order_id="PROF-001", sale_price_usd=50.0)
    oid2 = await db.add_order(ebay_order_id="PROF-002", sale_price_usd=80.0)
    await db.add_order(ebay_order_id="PROF-003", sale_price_usd=40.0)

    await db.update_order(oid1, status="completed", net_profit_jpy=3000)
    await db.update_order(oid2, status="completed", net_profit_jpy=5000)

    total = await db.get_total_completed_profit()
    assert total == 8000


async def test_get_total_completed_profit_returns_zero_when_no_completed(db):
    await db.add_order(ebay_order_id="PROF-004", sale_price_usd=50.0)
    total = await db.get_total_completed_profit()
    assert total == 0


# --- Listings ---


async def _create_candidate(db) -> int:
    """Helper to create a candidate for listing tests."""
    return await db.add_candidate(
        item_code="B09LISTING",
        source_site="amazon",
        title_jp="出品テスト商品",
        title_en="Listing Test Product",
        cost_jpy=3000,
        ebay_price_usd=80.0,
        net_profit_jpy=5000,
        margin_rate=1.67,
        weight_g=500,
    )


async def test_add_listing_returns_id(db):
    cid = await _create_candidate(db)
    lid = await db.add_listing(
        candidate_id=cid,
        sku="ECHUB-1",
        title_en="Test Product",
        listed_price_usd=80.0,
        listed_fx_rate=150.0,
    )
    assert lid is not None
    assert isinstance(lid, int)


async def test_get_listing_by_id_returns_listing(db):
    cid = await _create_candidate(db)
    lid = await db.add_listing(
        candidate_id=cid,
        sku="ECHUB-2",
        title_en="Test Product",
        listed_price_usd=80.0,
        listed_fx_rate=150.0,
        offer_id="OFF-123",
        listing_id="LIST-456",
        description_html="<p>Test</p>",
    )
    result = await db.get_listing_by_id(lid)
    assert result is not None
    assert result["sku"] == "ECHUB-2"
    assert result["candidate_id"] == cid
    assert result["offer_id"] == "OFF-123"
    assert result["listing_id"] == "LIST-456"
    assert result["listed_price_usd"] == 80.0
    assert result["status"] == "active"


async def test_get_listing_by_id_returns_none_when_not_exists(db):
    result = await db.get_listing_by_id(99999)
    assert result is None


async def test_get_listing_by_sku_returns_listing(db):
    cid = await _create_candidate(db)
    await db.add_listing(
        candidate_id=cid,
        sku="ECHUB-SKU-1",
        title_en="SKU Test",
        listed_price_usd=50.0,
        listed_fx_rate=150.0,
    )
    result = await db.get_listing_by_sku("ECHUB-SKU-1")
    assert result is not None
    assert result["sku"] == "ECHUB-SKU-1"


async def test_get_listing_by_sku_returns_none_when_not_exists(db):
    result = await db.get_listing_by_sku("NONEXISTENT")
    assert result is None


async def test_update_listing(db):
    cid = await _create_candidate(db)
    lid = await db.add_listing(
        candidate_id=cid,
        sku="ECHUB-UPD",
        title_en="Update Test",
        listed_price_usd=50.0,
        listed_fx_rate=150.0,
    )
    await db.update_listing(lid, offer_id="OFF-NEW", listing_id="LIST-NEW", status="ended")
    result = await db.get_listing_by_id(lid)
    assert result["offer_id"] == "OFF-NEW"
    assert result["listing_id"] == "LIST-NEW"
    assert result["status"] == "ended"


async def test_add_order_with_listing_id(db):
    cid = await _create_candidate(db)
    lid = await db.add_listing(
        candidate_id=cid,
        sku="ECHUB-ORD",
        title_en="Order Link Test",
        listed_price_usd=80.0,
        listed_fx_rate=150.0,
    )
    oid = await db.add_order(
        ebay_order_id="ORD-LID-001",
        candidate_id=cid,
        listing_id=lid,
        sale_price_usd=80.0,
    )
    order = await db.get_order_by_id(oid)
    assert order["listing_id"] == lid
    assert order["candidate_id"] == cid


async def test_add_message_with_listing_id(db):
    cid = await _create_candidate(db)
    lid = await db.add_listing(
        candidate_id=cid,
        sku="ECHUB-MSG",
        title_en="Message Link Test",
        listed_price_usd=80.0,
        listed_fx_rate=150.0,
    )
    oid = await db.add_order(
        ebay_order_id="ORD-MSG-001",
        candidate_id=cid,
        listing_id=lid,
        sale_price_usd=80.0,
    )
    mid = await db.add_message(
        buyer_username="buyer_trace",
        body="Test message",
        order_id=oid,
        listing_id=lid,
    )
    msg = await db.get_message_by_id(mid)
    assert msg["listing_id"] == lid
