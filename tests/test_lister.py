"""Lister モジュールのテスト."""

import pytest

from ec_hub.db import Database
from ec_hub.modules.lister import Lister


@pytest.fixture
def fee_rules():
    return {
        "ebay_fees": {"default_rate": 0.1325},
        "payoneer": {"rate": 0.02},
        "fx_buffer": {"rate": 0.03},
        "packing": {"default_cost": 200},
        "shipping": {
            "zones": {
                "US": [
                    {"max_weight_g": 500, "cost": 1500},
                    {"max_weight_g": 1000, "cost": 2000},
                ],
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
        "listing": {"max_daily_listings": 10, "limit_warning_threshold": 3},
        "ebay": {},
        "deepl": {},
        "line": {},
    }


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.close()


@pytest.fixture
def lister(db, settings, fee_rules):
    return Lister(db, settings, fee_rules)


def test_generate_listing_description(lister):
    html = lister.generate_listing_description(
        title_en="Test Product",
        title_jp="テスト商品",
        condition="New",
    )
    assert "Test Product" in html
    assert "テスト商品" in html
    assert "Authentic item from Japan" in html
    assert "Ships from" in html


def test_calc_listing_price(lister):
    """仕入¥3,000, 500g, 1USD=150JPY で利益率30%以上の価格を返す."""
    price = lister.calc_listing_price(cost_jpy=3000, weight_g=500, fx_rate=150.0)
    assert price > 0

    # 逆検証: この価格で利益率30%以上になるか
    jpy_revenue = price * 150.0
    ebay_fee = jpy_revenue * 0.1325
    payoneer_fee = jpy_revenue * 0.02
    fx_buffer = jpy_revenue * 0.03
    shipping = 1500
    packing = 200
    total_cost = 3000 + ebay_fee + payoneer_fee + shipping + packing + fx_buffer
    net_profit = jpy_revenue - total_cost
    margin = net_profit / 3000
    assert margin >= 0.30


def test_calc_listing_price_minimum(lister):
    """最低価格は$0.99."""
    price = lister.calc_listing_price(cost_jpy=1, weight_g=100, fx_rate=150.0)
    assert price >= 0.99


async def test_list_candidate_no_approved(lister):
    """承認済み候補がない場合はFalse."""
    result = await lister.list_candidate(999)
    assert result is False


async def test_list_candidate_simulation(lister, db):
    """eBay API未設定時はシミュレーションモードで出品."""
    cid = await db.add_candidate(
        item_code="B09TEST",
        source_site="amazon",
        title_jp="テスト商品",
        title_en=None,
        cost_jpy=3000,
        ebay_price_usd=80.0,
        net_profit_jpy=5000,
        margin_rate=1.67,
        weight_g=500,
    )
    await db.update_candidate_status(cid, "approved")

    result = await lister.list_candidate(cid)
    assert result is True

    candidates = await db.get_candidates(status="listed")
    assert len(candidates) == 1


async def test_check_selling_limit_unconfigured(lister):
    """eBay API未設定時のデフォルト値."""
    limit = await lister.check_selling_limit()
    assert limit["remaining"] == 100


async def test_run_with_approved(lister, db):
    """承認済み候補がある場合の出品."""
    for i in range(3):
        cid = await db.add_candidate(
            item_code=f"B09TEST{i}",
            source_site="amazon",
            title_jp=f"テスト商品{i}",
            title_en=None,
            cost_jpy=3000,
            ebay_price_usd=80.0,
            net_profit_jpy=5000,
            margin_rate=1.67,
        )
        await db.update_candidate_status(cid, "approved")

    count = await lister.run()
    assert count == 3


async def test_list_candidate_creates_listing_record(lister, db):
    """出品時にlistingsテーブルにレコードが作成される."""
    cid = await db.add_candidate(
        item_code="B09TRACE",
        source_site="amazon",
        title_jp="トレーサビリティ商品",
        title_en=None,
        cost_jpy=3000,
        ebay_price_usd=80.0,
        net_profit_jpy=5000,
        margin_rate=1.67,
        weight_g=500,
    )
    await db.update_candidate_status(cid, "approved")

    result = await lister.list_candidate(cid)
    assert result is True

    listing = await db.get_listing_by_sku(f"ECHUB-{cid}")
    assert listing is not None
    assert listing["candidate_id"] == cid
    assert listing["listed_price_usd"] > 0
    assert listing["listed_fx_rate"] > 0
    assert listing["title_en"] is not None
    assert listing["description_html"] is not None
    assert listing["status"] == "active"
