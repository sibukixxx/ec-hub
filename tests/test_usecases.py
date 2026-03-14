"""UseCase 層のテスト."""

import pytest

from ec_hub.context import AppContext
from ec_hub.exceptions import InvalidStatusError, NotFoundError
from ec_hub.usecases.dashboard import DashboardUseCase
from ec_hub.usecases.export import ExportUseCase
from ec_hub.usecases.message import MessageUseCase
from ec_hub.usecases.order import OrderUseCase
from ec_hub.usecases.profit_calc import ProfitCalcUseCase


@pytest.fixture
async def ctx():
    context = AppContext.create(db_path=":memory:")
    await context.connect()
    yield context
    await context.close()


# --- DashboardUseCase ---


class TestDashboardUseCase:
    async def test_returns_summary_with_counts(self, ctx):
        # Add test data
        await ctx.candidates.add(
            item_code="DASH01",
            source_site="amazon",
            title_jp="ダッシュ1",
            title_en=None,
            cost_jpy=1000,
            ebay_price_usd=30.0,
            net_profit_jpy=1000,
            margin_rate=1.0,
        )
        cid = await ctx.candidates.add(
            item_code="DASH02",
            source_site="amazon",
            title_jp="ダッシュ2",
            title_en=None,
            cost_jpy=2000,
            ebay_price_usd=60.0,
            net_profit_jpy=2000,
            margin_rate=1.0,
        )
        await ctx.candidates.update_status(cid, "approved")

        uc = DashboardUseCase(ctx)
        result = await uc.get_summary()

        assert result["candidates"]["pending"] == 1
        assert result["candidates"]["approved"] == 1
        assert result["candidates"]["listed"] == 0
        assert result["orders"]["awaiting_purchase"] == 0
        assert "fx_rate" in result

    async def test_returns_empty_summary(self, ctx):
        uc = DashboardUseCase(ctx)
        result = await uc.get_summary()
        assert result["candidates"]["pending"] == 0
        assert result["orders"]["completed"] == 0
        assert result["recent_profit"] == 0


# --- OrderUseCase ---


class TestOrderUseCase:
    async def test_get_order_returns_order(self, ctx):
        oid = await ctx.orders.add(
            ebay_order_id="UC-ORD-001",
            sale_price_usd=50.0,
        )
        uc = OrderUseCase(ctx)
        result = await uc.get_order(oid)
        assert result["ebay_order_id"] == "UC-ORD-001"

    async def test_get_order_raises_not_found(self, ctx):
        uc = OrderUseCase(ctx)
        with pytest.raises(NotFoundError):
            await uc.get_order(9999)

    async def test_list_orders(self, ctx):
        await ctx.orders.add(ebay_order_id="UC-LIST-01", sale_price_usd=40.0)
        await ctx.orders.add(ebay_order_id="UC-LIST-02", sale_price_usd=50.0)
        uc = OrderUseCase(ctx)
        results = await uc.list_orders()
        assert len(results) == 2

    async def test_update_status_invalid_raises(self, ctx):
        oid = await ctx.orders.add(ebay_order_id="UC-INV-01", sale_price_usd=40.0)
        uc = OrderUseCase(ctx)
        with pytest.raises(InvalidStatusError):
            await uc.update_status(oid, "invalid_status")

    async def test_update_status_not_found_raises(self, ctx):
        uc = OrderUseCase(ctx)
        with pytest.raises(NotFoundError):
            await uc.update_status(9999, "shipped")


# --- MessageUseCase ---


class TestMessageUseCase:
    async def test_list_messages(self, ctx):
        await ctx.messages.add(buyer_username="buyer1", body="Hello")
        uc = MessageUseCase(ctx)
        results = await uc.list_messages()
        assert len(results) == 1

    async def test_reply_returns_reply_data(self, ctx):
        mid = await ctx.messages.add(buyer_username="buyer1", body="Question?")
        uc = MessageUseCase(ctx)
        result = await uc.reply(mid, "Answer!")
        assert result["direction"] == "outbound"
        assert result["body"] == "Answer!"
        assert result["buyer_username"] == "buyer1"

    async def test_reply_preserves_traceability_links(self, ctx):
        cid = await ctx.candidates.add(
            item_code="MSG-UC-01",
            source_site="amazon",
            title_jp="msg",
            title_en="msg",
            cost_jpy=1000,
            ebay_price_usd=30.0,
            net_profit_jpy=1000,
            margin_rate=1.0,
        )
        lid = await ctx.db.add_listing(
            candidate_id=cid,
            sku=f"ECHUB-{cid}",
            title_en="msg",
            listed_price_usd=30.0,
            listed_fx_rate=150.0,
        )
        oid = await ctx.orders.add(
            ebay_order_id="MSG-ORD-01",
            listing_id=lid,
            sale_price_usd=30.0,
        )
        mid = await ctx.messages.add(
            buyer_username="buyer1",
            body="Question?",
            order_id=oid,
        )

        uc = MessageUseCase(ctx)
        result = await uc.reply(mid, "Answer!")

        assert result["order_id"] == oid
        assert result["listing_id"] == lid
        assert result["candidate_id"] == cid

    async def test_reply_raises_not_found(self, ctx):
        uc = MessageUseCase(ctx)
        with pytest.raises(NotFoundError):
            await uc.reply(9999, "body")


# --- ExportUseCase ---


class TestExportUseCase:
    async def test_export_candidates_csv(self, ctx):
        await ctx.candidates.add(
            item_code="EXP01",
            source_site="amazon",
            title_jp="エクスポート",
            title_en=None,
            cost_jpy=1000,
            ebay_price_usd=30.0,
            net_profit_jpy=1000,
            margin_rate=1.0,
        )
        uc = ExportUseCase(ctx)
        content, media_type = await uc.export_data("candidates", "csv")
        assert media_type == "text/csv"
        assert "EXP01" in content

    async def test_export_orders_json(self, ctx):
        await ctx.orders.add(ebay_order_id="EXP-ORD-01", sale_price_usd=40.0)
        uc = ExportUseCase(ctx)
        content, media_type = await uc.export_data("orders", "json")
        assert media_type == "application/json"
        assert "EXP-ORD-01" in content

    async def test_export_invalid_type_raises(self, ctx):
        uc = ExportUseCase(ctx)
        with pytest.raises(ValueError, match="Invalid type"):
            await uc.export_data("invalid", "csv")

    async def test_export_invalid_format_raises(self, ctx):
        uc = ExportUseCase(ctx)
        with pytest.raises(ValueError, match="Invalid format"):
            await uc.export_data("candidates", "xml")


# --- ProfitCalcUseCase ---


class TestProfitCalcUseCase:
    async def test_calculate_returns_breakdown(self, ctx):
        uc = ProfitCalcUseCase(ctx)
        result = await uc.calculate(cost_jpy=3000, ebay_price_usd=80.0, weight_g=500, destination="US")
        assert "net_profit" in result
        assert "margin_rate" in result
        assert "fx_rate" in result
