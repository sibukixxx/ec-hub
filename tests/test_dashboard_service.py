"""DashboardService のテスト."""

import pytest

from ec_hub.context import AppContext
from ec_hub.db import Database
from ec_hub.services.dashboard_service import DashboardService


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
                "US": [{"max_weight_g": 500, "cost": 1500}, {"max_weight_g": 1000, "cost": 2000}],
                "OTHER": [{"max_weight_g": 500, "cost": 2000}],
            },
            "destination_zones": {"US": "US"},
        },
    }


@pytest.fixture
async def ctx(test_settings, test_fee_rules):
    db = Database(':memory:')

    await db.connect()

    ctx = AppContext(db=db,
        settings=test_settings,
        fee_rules=test_fee_rules,
    )
    yield ctx
    await ctx.close()


async def test_get_dashboard_summary_empty(ctx):
    svc = DashboardService(ctx)
    summary = await svc.get_dashboard_summary()
    assert summary["candidates"]["pending"] == 0
    assert summary["orders"]["completed"] == 0
    assert summary["recent_profit"] == 0
    assert summary["fx_rate"] > 0


async def test_get_dashboard_summary_with_data(ctx):
    await ctx.db.add_candidate(
        item_code="D1", source_site="amazon", title_jp="a", title_en=None,
        cost_jpy=1000, ebay_price_usd=30.0, net_profit_jpy=500, margin_rate=0.5,
    )
    oid = await ctx.db.add_order(
        ebay_order_id="DASH-001", buyer_username="b", sale_price_usd=50.0,
    )
    await ctx.db.update_order(oid, status="completed", net_profit_jpy=3000)

    svc = DashboardService(ctx)
    summary = await svc.get_dashboard_summary()
    assert summary["candidates"]["pending"] == 1
    assert summary["orders"]["completed"] == 1
    assert summary["recent_profit"] == 3000


async def test_calc_profit(ctx):
    svc = DashboardService(ctx)
    breakdown = await svc.calc_profit(
        cost_jpy=3000, ebay_price_usd=50.0, weight_g=500, destination="US",
    )
    assert breakdown.net_profit != 0
    assert breakdown.fx_rate > 0
    assert breakdown.margin_rate != 0
