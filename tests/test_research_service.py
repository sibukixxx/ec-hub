"""ResearchService のテスト."""

import pytest

from ec_hub.context import AppContext
from ec_hub.db import Database
from ec_hub.services.research_service import ResearchService


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


async def test_get_candidates_empty(ctx):
    svc = ResearchService(ctx)
    result = await svc.get_candidates()
    assert result == []


async def test_get_candidates_with_data(ctx):
    await ctx.db.add_candidate(
        item_code="RS-001", source_site="amazon", title_jp="テスト",
        title_en=None, cost_jpy=1000, ebay_price_usd=30.0,
        net_profit_jpy=500, margin_rate=0.5,
    )
    svc = ResearchService(ctx)
    result = await svc.get_candidates()
    assert len(result) == 1
    assert result[0]["item_code"] == "RS-001"


async def test_get_candidates_by_status(ctx):
    cid = await ctx.db.add_candidate(
        item_code="RS-002", source_site="amazon", title_jp="テスト2",
        title_en=None, cost_jpy=2000, ebay_price_usd=60.0,
        net_profit_jpy=1000, margin_rate=0.5,
    )
    await ctx.db.update_candidate_status(cid, "approved")

    svc = ResearchService(ctx)
    approved = await svc.get_candidates(status="approved")
    assert len(approved) == 1
    pending = await svc.get_candidates(status="pending")
    assert len(pending) == 0


async def test_get_candidate_by_id(ctx):
    cid = await ctx.db.add_candidate(
        item_code="RS-003", source_site="amazon", title_jp="テスト3",
        title_en=None, cost_jpy=3000, ebay_price_usd=90.0,
        net_profit_jpy=1500, margin_rate=0.5,
    )
    svc = ResearchService(ctx)
    result = await svc.get_candidate(cid)
    assert result is not None
    assert result["item_code"] == "RS-003"


async def test_get_candidate_by_id_not_found(ctx):
    svc = ResearchService(ctx)
    result = await svc.get_candidate(99999)
    assert result is None


async def test_update_candidate_status(ctx):
    cid = await ctx.db.add_candidate(
        item_code="RS-004", source_site="rakuten", title_jp="テスト4",
        title_en=None, cost_jpy=4000, ebay_price_usd=120.0,
        net_profit_jpy=2000, margin_rate=0.5,
    )
    svc = ResearchService(ctx)
    await svc.update_candidate_status(cid, "approved")
    result = await svc.get_candidate(cid)
    assert result["status"] == "approved"


# --- research_runs ---


async def test_get_research_runs_empty(ctx):
    svc = ResearchService(ctx)
    result = await svc.get_research_runs()
    assert result == []


async def test_get_research_runs_with_data(ctx):
    await ctx.db.create_research_run(query="test", ebay_results_count=10)
    svc = ResearchService(ctx)
    result = await svc.get_research_runs()
    assert len(result) == 1
    assert result[0]["query"] == "test"


async def test_get_research_run_by_id(ctx):
    run_id = await ctx.db.create_research_run(query="q1", ebay_results_count=5)
    svc = ResearchService(ctx)
    result = await svc.get_research_run(run_id)
    assert result is not None
    assert result["query"] == "q1"


async def test_get_research_run_not_found(ctx):
    svc = ResearchService(ctx)
    result = await svc.get_research_run(99999)
    assert result is None
