"""AppContext のテスト."""

import pytest

from ec_hub.context import AppContext


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


async def test_create_context_initializes_db(test_settings, test_fee_rules):
    ctx = await AppContext.create(
        settings=test_settings,
        fee_rules=test_fee_rules,
        db_path=":memory:",
    )
    try:
        assert ctx.db is not None
        # DB is connected and usable
        candidates = await ctx.db.get_candidates()
        assert candidates == []
    finally:
        await ctx.close()


async def test_context_provides_settings_and_fee_rules(test_settings, test_fee_rules):
    ctx = await AppContext.create(
        settings=test_settings,
        fee_rules=test_fee_rules,
        db_path=":memory:",
    )
    try:
        assert ctx.settings == test_settings
        assert ctx.fee_rules == test_fee_rules
    finally:
        await ctx.close()


async def test_context_async_context_manager(test_settings, test_fee_rules):
    async with await AppContext.create(
        settings=test_settings,
        fee_rules=test_fee_rules,
        db_path=":memory:",
    ) as ctx:
        assert ctx.db is not None
        cid = await ctx.db.add_candidate(
            item_code="CTX-TEST",
            source_site="amazon",
            title_jp="コンテキストテスト",
            title_en=None,
            cost_jpy=1000,
            ebay_price_usd=30.0,
            net_profit_jpy=500,
            margin_rate=0.5,
        )
        assert cid is not None
