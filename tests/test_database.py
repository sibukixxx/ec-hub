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


# --- research_runs ---


async def test_create_research_run(db):
    run_id = await db.create_research_run(
        query="japanese vintage",
        ebay_results_count=20,
    )
    assert run_id is not None
    assert run_id > 0


async def test_complete_research_run(db):
    run_id = await db.create_research_run(
        query="anime figure",
        ebay_results_count=15,
    )
    await db.complete_research_run(run_id, candidates_found=5)
    run = await db.get_research_run(run_id)
    assert run is not None
    assert run["query"] == "anime figure"
    assert run["ebay_results_count"] == 15
    assert run["candidates_found"] == 5
    assert run["completed_at"] is not None


async def test_get_research_runs(db):
    await db.create_research_run(query="q1", ebay_results_count=10)
    await db.create_research_run(query="q2", ebay_results_count=20)
    runs = await db.get_research_runs(limit=10)
    assert len(runs) == 2


# --- candidate provenance (ebay_item_id, research_run_id) ---


async def test_add_candidate_with_provenance(db):
    run_id = await db.create_research_run(query="test", ebay_results_count=5)
    cid = await db.add_candidate(
        item_code="B09PROV",
        source_site="amazon",
        title_jp="出所テスト商品",
        title_en=None,
        cost_jpy=3000,
        ebay_price_usd=80.0,
        net_profit_jpy=5000,
        margin_rate=1.67,
        ebay_item_id="eBay123456",
        ebay_title="eBay Test Product",
        ebay_url="https://www.ebay.com/itm/123456",
        research_run_id=run_id,
    )
    candidate = await db.get_candidate_by_id(cid)
    assert candidate["ebay_item_id"] == "eBay123456"
    assert candidate["ebay_title"] == "eBay Test Product"
    assert candidate["ebay_url"] == "https://www.ebay.com/itm/123456"
    assert candidate["research_run_id"] == run_id


# --- upsert (dedup) ---


async def test_upsert_candidate_creates_new_when_not_exists(db):
    cid = await db.upsert_candidate(
        item_code="UPSERT001",
        source_site="amazon",
        ebay_item_id="EBAY001",
        title_jp="新規候補",
        title_en=None,
        cost_jpy=3000,
        ebay_price_usd=80.0,
        net_profit_jpy=5000,
        margin_rate=1.67,
    )
    assert cid is not None
    candidates = await db.get_candidates()
    assert len(candidates) == 1


async def test_upsert_candidate_updates_existing(db):
    cid1 = await db.upsert_candidate(
        item_code="UPSERT002",
        source_site="amazon",
        ebay_item_id="EBAY002",
        title_jp="初回登録",
        title_en=None,
        cost_jpy=3000,
        ebay_price_usd=80.0,
        net_profit_jpy=5000,
        margin_rate=1.67,
    )
    cid2 = await db.upsert_candidate(
        item_code="UPSERT002",
        source_site="amazon",
        ebay_item_id="EBAY002",
        title_jp="初回登録",
        title_en=None,
        cost_jpy=2800,
        ebay_price_usd=85.0,
        net_profit_jpy=6000,
        margin_rate=2.14,
    )
    # Same row should be updated, not duplicated
    assert cid1 == cid2
    candidates = await db.get_candidates()
    assert len(candidates) == 1
    assert candidates[0]["cost_jpy"] == 2800
    assert candidates[0]["ebay_price_usd"] == 85.0


async def test_upsert_candidate_different_ebay_item_creates_new(db):
    """同じ仕入れ商品でもeBay商品が異なれば別候補."""
    await db.upsert_candidate(
        item_code="UPSERT003",
        source_site="amazon",
        ebay_item_id="EBAY_A",
        title_jp="商品A",
        title_en=None,
        cost_jpy=3000,
        ebay_price_usd=80.0,
        net_profit_jpy=5000,
        margin_rate=1.67,
    )
    await db.upsert_candidate(
        item_code="UPSERT003",
        source_site="amazon",
        ebay_item_id="EBAY_B",
        title_jp="商品A",
        title_en=None,
        cost_jpy=3000,
        ebay_price_usd=90.0,
        net_profit_jpy=6000,
        margin_rate=2.0,
    )
    candidates = await db.get_candidates()
    assert len(candidates) == 2
