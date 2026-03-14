"""候補の出所トレーサビリティと重複排除のテスト (Issue #012)."""

import pytest

from ec_hub.db import Database


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.close()


# --- research_runs テスト ---


async def test_create_research_run(db):
    """research_runs テーブルに実行記録を保存できる."""
    run_id = await db.create_research_run(
        query="japanese vintage",
        ebay_hits=25,
        candidates_found=3,
    )
    assert run_id is not None
    assert run_id > 0


async def test_get_research_runs(db):
    """research_runs の一覧を取得できる."""
    await db.create_research_run(query="anime figure", ebay_hits=10, candidates_found=2)
    await db.create_research_run(query="japan exclusive", ebay_hits=15, candidates_found=1)

    runs = await db.get_research_runs(limit=10)
    assert len(runs) == 2
    assert runs[0]["query"] == "japan exclusive"  # newest first
    assert runs[1]["query"] == "anime figure"


# --- candidates に eBay 出所情報を保存 ---


async def test_add_candidate_with_ebay_provenance(db):
    """候補登録時に eBay 出所情報を保存できる."""
    run_id = await db.create_research_run(query="test", ebay_hits=5, candidates_found=1)
    cid = await db.add_candidate(
        item_code="B09TEST",
        source_site="amazon",
        title_jp="テスト商品",
        title_en=None,
        cost_jpy=3000,
        ebay_price_usd=80.0,
        net_profit_jpy=5000,
        margin_rate=0.50,
        ebay_item_id="eBay123456",
        ebay_title="Test Product From Japan",
        ebay_url="https://www.ebay.com/itm/123456",
        research_run_id=run_id,
    )
    assert cid is not None

    candidates = await db.get_candidates()
    c = candidates[0]
    assert c["ebay_item_id"] == "eBay123456"
    assert c["ebay_title"] == "Test Product From Japan"
    assert c["ebay_url"] == "https://www.ebay.com/itm/123456"
    assert c["research_run_id"] == run_id


# --- 重複排除 (upsert) ---


async def test_upsert_candidate_deduplicates(db):
    """同一 source_site + item_code + ebay_item_id は重複登録されない."""
    run_id = await db.create_research_run(query="test", ebay_hits=5, candidates_found=1)

    # 1回目: 新規登録
    cid1 = await db.add_candidate(
        item_code="B09TEST",
        source_site="amazon",
        title_jp="テスト商品",
        title_en=None,
        cost_jpy=3000,
        ebay_price_usd=80.0,
        net_profit_jpy=5000,
        margin_rate=0.50,
        ebay_item_id="eBay123",
        ebay_title="Test Product",
        ebay_url="https://www.ebay.com/itm/123",
        research_run_id=run_id,
    )

    # 2回目: 同一キーで価格が変わった
    run_id2 = await db.create_research_run(query="test2", ebay_hits=3, candidates_found=1)
    cid2 = await db.add_candidate(
        item_code="B09TEST",
        source_site="amazon",
        title_jp="テスト商品",
        title_en=None,
        cost_jpy=2800,  # price changed
        ebay_price_usd=85.0,  # price changed
        net_profit_jpy=6000,
        margin_rate=0.55,
        ebay_item_id="eBay123",
        ebay_title="Test Product",
        ebay_url="https://www.ebay.com/itm/123",
        research_run_id=run_id2,
    )

    # 重複せず1件のまま
    candidates = await db.get_candidates()
    assert len(candidates) == 1

    # 価格は最新に更新されている
    c = candidates[0]
    assert c["cost_jpy"] == 2800
    assert c["ebay_price_usd"] == 85.0
    assert c["net_profit_jpy"] == 6000
    assert c["margin_rate"] == 0.55
    assert c["research_run_id"] == run_id2

    # IDは同じ
    assert cid1 == cid2


async def test_upsert_different_ebay_item_creates_new(db):
    """同じ仕入れ商品でも異なる eBay 商品なら別候補として登録."""
    run_id = await db.create_research_run(query="test", ebay_hits=5, candidates_found=2)

    await db.add_candidate(
        item_code="B09TEST",
        source_site="amazon",
        title_jp="テスト商品",
        title_en=None,
        cost_jpy=3000,
        ebay_price_usd=80.0,
        net_profit_jpy=5000,
        margin_rate=0.50,
        ebay_item_id="eBay111",
        ebay_title="Product A",
        ebay_url="https://www.ebay.com/itm/111",
        research_run_id=run_id,
    )
    await db.add_candidate(
        item_code="B09TEST",
        source_site="amazon",
        title_jp="テスト商品",
        title_en=None,
        cost_jpy=3000,
        ebay_price_usd=90.0,
        net_profit_jpy=6000,
        margin_rate=0.55,
        ebay_item_id="eBay222",  # different eBay item
        ebay_title="Product B",
        ebay_url="https://www.ebay.com/itm/222",
        research_run_id=run_id,
    )

    candidates = await db.get_candidates()
    assert len(candidates) == 2


async def test_upsert_preserves_status(db):
    """upsert 時に approved 等のステータスは上書きしない."""
    run_id = await db.create_research_run(query="test", ebay_hits=5, candidates_found=1)

    cid = await db.add_candidate(
        item_code="B09TEST",
        source_site="amazon",
        title_jp="テスト商品",
        title_en=None,
        cost_jpy=3000,
        ebay_price_usd=80.0,
        net_profit_jpy=5000,
        margin_rate=0.50,
        ebay_item_id="eBay123",
        ebay_title="Test",
        ebay_url="https://www.ebay.com/itm/123",
        research_run_id=run_id,
    )
    await db.update_candidate_status(cid, "approved")

    # Re-observe with different price
    run_id2 = await db.create_research_run(query="test2", ebay_hits=3, candidates_found=1)
    await db.add_candidate(
        item_code="B09TEST",
        source_site="amazon",
        title_jp="テスト商品",
        title_en=None,
        cost_jpy=2800,
        ebay_price_usd=85.0,
        net_profit_jpy=6000,
        margin_rate=0.55,
        ebay_item_id="eBay123",
        ebay_title="Test",
        ebay_url="https://www.ebay.com/itm/123",
        research_run_id=run_id2,
    )

    candidates = await db.get_candidates()
    assert len(candidates) == 1
    assert candidates[0]["status"] == "approved"  # status preserved


# --- 後方互換: ebay_item_id なしの場合 ---


async def test_add_candidate_without_ebay_provenance(db):
    """eBay 出所情報なしでも従来通り登録できる."""
    cid = await db.add_candidate(
        item_code="B09TEST",
        source_site="amazon",
        title_jp="テスト商品",
        title_en=None,
        cost_jpy=3000,
        ebay_price_usd=80.0,
        net_profit_jpy=5000,
        margin_rate=0.50,
    )
    assert cid is not None

    candidates = await db.get_candidates()
    assert len(candidates) == 1
    assert candidates[0]["ebay_item_id"] is None
