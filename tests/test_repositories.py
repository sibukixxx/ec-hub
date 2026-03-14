"""Repository 層のテスト."""

import pytest

from ec_hub.db import Database
from ec_hub.repositories import CandidateRepository, MessageRepository, OrderRepository


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.close()


# --- CandidateRepository ---


class TestCandidateRepository:
    async def test_get_by_id_returns_candidate_when_exists(self, db):
        repo = CandidateRepository(db)
        cid = await db.add_candidate(
            item_code="REPO01",
            source_site="amazon",
            title_jp="Repo商品",
            title_en="Repo Product",
            cost_jpy=3000,
            ebay_price_usd=80.0,
            net_profit_jpy=5000,
            margin_rate=1.5,
        )
        result = await repo.get_by_id(cid)
        assert result is not None
        assert result["id"] == cid
        assert result["item_code"] == "REPO01"

    async def test_get_by_id_returns_none_when_not_exists(self, db):
        repo = CandidateRepository(db)
        assert await repo.get_by_id(9999) is None

    async def test_list_returns_all(self, db):
        repo = CandidateRepository(db)
        await db.add_candidate(
            item_code="LIST01",
            source_site="amazon",
            title_jp="一覧1",
            title_en=None,
            cost_jpy=1000,
            ebay_price_usd=30.0,
            net_profit_jpy=1000,
            margin_rate=1.0,
        )
        await db.add_candidate(
            item_code="LIST02",
            source_site="rakuten",
            title_jp="一覧2",
            title_en=None,
            cost_jpy=2000,
            ebay_price_usd=60.0,
            net_profit_jpy=2000,
            margin_rate=1.0,
        )
        results = await repo.list()
        assert len(results) == 2

    async def test_list_filters_by_status(self, db):
        repo = CandidateRepository(db)
        cid = await db.add_candidate(
            item_code="FILT01",
            source_site="amazon",
            title_jp="フィルタ",
            title_en=None,
            cost_jpy=1000,
            ebay_price_usd=30.0,
            net_profit_jpy=1000,
            margin_rate=1.0,
        )
        await db.update_candidate_status(cid, "approved")
        assert len(await repo.list(status="approved")) == 1
        assert len(await repo.list(status="pending")) == 0

    async def test_count_by_status(self, db):
        repo = CandidateRepository(db)
        assert await repo.count_by_status() == 0
        await db.add_candidate(
            item_code="CNT01",
            source_site="amazon",
            title_jp="カウント",
            title_en=None,
            cost_jpy=1000,
            ebay_price_usd=30.0,
            net_profit_jpy=1000,
            margin_rate=1.0,
        )
        assert await repo.count_by_status() == 1
        assert await repo.count_by_status("pending") == 1
        assert await repo.count_by_status("approved") == 0

    async def test_update_status(self, db):
        repo = CandidateRepository(db)
        cid = await db.add_candidate(
            item_code="UPD01",
            source_site="amazon",
            title_jp="更新",
            title_en=None,
            cost_jpy=1000,
            ebay_price_usd=30.0,
            net_profit_jpy=1000,
            margin_rate=1.0,
        )
        await repo.update_status(cid, "approved")
        result = await repo.get_by_id(cid)
        assert result["status"] == "approved"


# --- OrderRepository ---


class TestOrderRepository:
    async def test_get_by_id_returns_order_when_exists(self, db):
        repo = OrderRepository(db)
        oid = await db.add_order(
            ebay_order_id="ORD-001",
            sale_price_usd=50.0,
            buyer_username="buyer1",
            destination_country="US",
        )
        result = await repo.get_by_id(oid)
        assert result is not None
        assert result["id"] == oid
        assert result["ebay_order_id"] == "ORD-001"

    async def test_get_by_id_returns_none_when_not_exists(self, db):
        repo = OrderRepository(db)
        assert await repo.get_by_id(9999) is None

    async def test_list_returns_all(self, db):
        repo = OrderRepository(db)
        await db.add_order(ebay_order_id="ORD-L01", sale_price_usd=40.0)
        await db.add_order(ebay_order_id="ORD-L02", sale_price_usd=50.0)
        results = await repo.list()
        assert len(results) == 2

    async def test_list_filters_by_status(self, db):
        repo = OrderRepository(db)
        await db.add_order(ebay_order_id="ORD-F01", sale_price_usd=40.0)
        oid = await db.add_order(ebay_order_id="ORD-F02", sale_price_usd=50.0)
        await db.update_order(oid, status="shipped")
        assert len(await repo.list(status="awaiting_purchase")) == 1
        assert len(await repo.list(status="shipped")) == 1

    async def test_count_by_status(self, db):
        repo = OrderRepository(db)
        assert await repo.count_by_status() == 0
        await db.add_order(ebay_order_id="ORD-C01", sale_price_usd=40.0)
        assert await repo.count_by_status() == 1
        assert await repo.count_by_status("awaiting_purchase") == 1
        assert await repo.count_by_status("shipped") == 0

    async def test_update(self, db):
        repo = OrderRepository(db)
        oid = await db.add_order(ebay_order_id="ORD-U01", sale_price_usd=40.0)
        await repo.update(oid, status="shipped", tracking_number="JP999")
        result = await repo.get_by_id(oid)
        assert result["status"] == "shipped"
        assert result["tracking_number"] == "JP999"


# --- MessageRepository ---


class TestMessageRepository:
    async def test_get_by_id_returns_message_when_exists(self, db):
        repo = MessageRepository(db)
        mid = await db.add_message(
            buyer_username="msg_buyer",
            body="Hello",
        )
        result = await repo.get_by_id(mid)
        assert result is not None
        assert result["id"] == mid
        assert result["body"] == "Hello"

    async def test_get_by_id_returns_none_when_not_exists(self, db):
        repo = MessageRepository(db)
        assert await repo.get_by_id(9999) is None

    async def test_list_returns_all(self, db):
        repo = MessageRepository(db)
        await db.add_message(buyer_username="b1", body="msg1")
        await db.add_message(buyer_username="b2", body="msg2")
        results = await repo.list()
        assert len(results) == 2

    async def test_list_filters_by_buyer(self, db):
        repo = MessageRepository(db)
        await db.add_message(buyer_username="alice", body="hi")
        await db.add_message(buyer_username="bob", body="hey")
        assert len(await repo.list(buyer_username="alice")) == 1
