"""AppContext のテスト."""

from pathlib import Path

import pytest

from ec_hub.context import AppContext
from ec_hub.repositories import CandidateRepository, MessageRepository, OrderRepository


@pytest.fixture
async def ctx():
    context = AppContext.create(db_path=":memory:")
    await context.connect()
    yield context
    await context.close()


async def test_create_app_context():
    ctx = AppContext.create(db_path=":memory:")
    assert ctx is not None
    assert ctx.db is not None


async def test_app_context_provides_repositories(ctx):
    assert isinstance(ctx.candidates, CandidateRepository)
    assert isinstance(ctx.orders, OrderRepository)
    assert isinstance(ctx.messages, MessageRepository)


async def test_app_context_db_is_connected(ctx):
    # DB が接続済みで操作可能なことを確認
    cid = await ctx.candidates.add(
        item_code="CTX01",
        source_site="amazon",
        title_jp="コンテキストテスト",
        title_en=None,
        cost_jpy=1000,
        ebay_price_usd=30.0,
        net_profit_jpy=1000,
        margin_rate=1.0,
    )
    result = await ctx.candidates.get_by_id(cid)
    assert result is not None
    assert result["item_code"] == "CTX01"


async def test_app_context_as_context_manager():
    async with AppContext.create(db_path=":memory:") as ctx:
        assert isinstance(ctx.candidates, CandidateRepository)
        cid = await ctx.candidates.add(
            item_code="CM01",
            source_site="amazon",
            title_jp="CMテスト",
            title_en=None,
            cost_jpy=1000,
            ebay_price_usd=30.0,
            net_profit_jpy=1000,
            margin_rate=1.0,
        )
        assert cid is not None


async def test_app_context_settings_and_fee_rules(ctx):
    assert ctx.settings is not None
    assert ctx.fee_rules is not None


def test_app_context_validate_services_fails_fast(tmp_path: Path):
    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text("database:\n  path: ':memory:'\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="Required service"):
        AppContext.create(settings_path=settings_path, db_path=":memory:", validate_services=True)
