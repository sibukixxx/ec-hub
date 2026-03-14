"""REST API のテスト."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from ec_hub.api import app, get_ctx
from ec_hub.context import AppContext
from ec_hub.db import Database


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
    db = Database(":memory:")
    await db.connect()
    ctx = AppContext(settings=test_settings, fee_rules=test_fee_rules, db=db)
    yield ctx
    await ctx.close()


@pytest.fixture
async def client(ctx):
    """FastAPI テストクライアント (dependency_overrides 方式)."""
    app.dependency_overrides[get_ctx] = lambda: ctx
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def test_dashboard_empty(client):
    resp = await client.get("/api/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["candidates"]["pending"] == 0
    assert data["orders"]["completed"] == 0
    assert data["recent_profit"] == 0
    assert data["fx_rate"] > 0


async def test_candidates_empty(client):
    resp = await client.get("/api/candidates")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_candidates_crud(client, ctx):
    cid = await ctx.db.add_candidate(
        item_code="B09TEST",
        source_site="amazon",
        title_jp="テスト商品",
        title_en=None,
        cost_jpy=3000,
        ebay_price_usd=80.0,
        net_profit_jpy=5000,
        margin_rate=1.67,
    )

    # List
    resp = await client.get("/api/candidates")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["item_code"] == "B09TEST"

    # Get
    resp = await client.get(f"/api/candidates/{cid}")
    assert resp.status_code == 200
    assert resp.json()["id"] == cid

    # Filter by status
    resp = await client.get("/api/candidates?status=pending")
    assert len(resp.json()) == 1

    resp = await client.get("/api/candidates?status=approved")
    assert len(resp.json()) == 0

    # Update status
    resp = await client.patch(
        f"/api/candidates/{cid}/status",
        json={"status": "approved"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    resp = await client.get("/api/candidates?status=approved")
    assert len(resp.json()) == 1


async def test_candidates_invalid_status(client, ctx):
    cid = await ctx.db.add_candidate(
        item_code="B09X",
        source_site="amazon",
        title_jp="test",
        title_en=None,
        cost_jpy=1000,
        ebay_price_usd=30.0,
        net_profit_jpy=1000,
        margin_rate=1.0,
    )
    resp = await client.patch(
        f"/api/candidates/{cid}/status",
        json={"status": "invalid_status"},
    )
    assert resp.status_code == 400


async def test_candidate_not_found(client):
    resp = await client.get("/api/candidates/99999")
    assert resp.status_code == 404


async def test_orders_empty(client):
    resp = await client.get("/api/orders")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_orders_list(client, ctx):
    await ctx.db.add_order(
        ebay_order_id="12-34567-89012",
        buyer_username="buyer1",
        sale_price_usd=80.0,
        destination_country="US",
    )
    resp = await client.get("/api/orders")
    assert resp.status_code == 200
    orders = resp.json()
    assert len(orders) == 1
    assert orders[0]["ebay_order_id"] == "12-34567-89012"


async def test_order_not_found(client):
    resp = await client.get("/api/orders/99999")
    assert resp.status_code == 404


async def test_calc_profit(client):
    resp = await client.post("/api/calc/profit", json={
        "cost_jpy": 3000,
        "ebay_price_usd": 50.0,
        "weight_g": 500,
        "destination": "US",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "net_profit" in data
    assert "margin_rate" in data
    assert data["fx_rate"] > 0
    assert data["jpy_revenue"] > 0


async def test_dashboard_with_data(client, ctx):
    """データがある場合のダッシュボード."""
    await ctx.db.add_candidate(
        item_code="C1", source_site="amazon", title_jp="a",
        title_en=None, cost_jpy=1000, ebay_price_usd=30.0,
        net_profit_jpy=1000, margin_rate=1.0,
    )
    oid = await ctx.db.add_order(
        ebay_order_id="DASH-001",
        buyer_username="b",
        sale_price_usd=50.0,
    )
    await ctx.db.update_order(oid, status="completed", net_profit_jpy=3000)

    resp = await client.get("/api/dashboard")
    data = resp.json()
    assert data["candidates"]["pending"] == 1
    assert data["orders"]["completed"] == 1
    assert data["recent_profit"] == 3000


# --- リサーチ API ---


@patch("ec_hub.usecases.research.ResearchUseCase.run", new_callable=AsyncMock)
async def test_research_run(mock_run_research, client):
    """POST /api/research/run returns registered count."""
    mock_run_research.return_value = 3

    resp = await client.post("/api/research/run", json={
        "keywords": ["test keyword"],
        "pages": 1,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["registered"] == 3
    assert data["status"] == "completed"


@patch("ec_hub.usecases.research.ResearchUseCase.run", new_callable=AsyncMock)
async def test_research_run_default_keywords(mock_run_research, client):
    """POST /api/research/run with no body uses defaults."""
    mock_run_research.return_value = 0

    resp = await client.post("/api/research/run", json={})
    assert resp.status_code == 200


# --- 出品 API ---


async def test_listing_run(client, ctx):
    """POST /api/listing/run lists approved candidates."""
    db = ctx.db
    cid = await db.add_candidate(
        item_code="LIST01", source_site="amazon", title_jp="出品テスト",
        title_en=None, cost_jpy=2000, ebay_price_usd=60.0,
        net_profit_jpy=3000, margin_rate=1.5,
    )
    await db.update_candidate_status(cid, "approved")

    resp = await client.post("/api/listing/run")
    assert resp.status_code == 200
    data = resp.json()
    assert "listed_count" in data


async def test_listing_limits(client):
    """GET /api/listing/limits returns selling limit info."""
    resp = await client.get("/api/listing/limits")
    assert resp.status_code == 200
    data = resp.json()
    assert "current" in data
    assert "max" in data
    assert "remaining" in data


# --- 注文管理 API ---


async def test_orders_check(client):
    """POST /api/orders/check checks for new orders."""
    resp = await client.post("/api/orders/check")
    assert resp.status_code == 200
    data = resp.json()
    assert "new_orders" in data


async def test_orders_status_update(client, ctx):
    """PUT /api/orders/{id}/status updates order status."""
    oid = await ctx.db.add_order(
        ebay_order_id="ORD-STATUS-001",
        buyer_username="buyer1",
        sale_price_usd=50.0,
        destination_country="US",
    )

    resp = await client.put(f"/api/orders/{oid}/status", json={
        "status": "purchased",
        "actual_cost_jpy": 3000,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "purchased"


async def test_orders_status_update_shipped(client, ctx):
    """PUT /api/orders/{id}/status with shipped status requires tracking."""
    oid = await ctx.db.add_order(
        ebay_order_id="ORD-SHIP-001",
        buyer_username="buyer2",
        sale_price_usd=60.0,
        destination_country="US",
    )
    await ctx.db.update_order(oid, status="purchased", actual_cost_jpy=2000)

    resp = await client.put(f"/api/orders/{oid}/status", json={
        "status": "shipped",
        "tracking_number": "JP123456789",
        "shipping_cost_jpy": 1500,
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "shipped"


async def test_orders_status_update_invalid(client, ctx):
    """PUT /api/orders/{id}/status rejects invalid status."""
    oid = await ctx.db.add_order(
        ebay_order_id="ORD-INV-001",
        buyer_username="buyer3",
        sale_price_usd=40.0,
    )
    resp = await client.put(f"/api/orders/{oid}/status", json={
        "status": "nonexistent",
    })
    assert resp.status_code == 400


async def test_orders_status_update_not_found(client):
    """PUT /api/orders/{id}/status returns 404 for missing order."""
    resp = await client.put("/api/orders/99999/status", json={
        "status": "purchased",
    })
    assert resp.status_code == 404


# --- メッセージ API ---


async def test_messages_empty(client):
    """GET /api/messages returns empty list initially."""
    resp = await client.get("/api/messages")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_messages_list(client, ctx):
    """GET /api/messages returns stored messages."""
    await ctx.db.add_message(
        buyer_username="testbuyer",
        body="When will my item ship?",
        category="shipping_tracking",
    )
    resp = await client.get("/api/messages")
    assert resp.status_code == 200
    messages = resp.json()
    assert len(messages) == 1
    assert messages[0]["buyer_username"] == "testbuyer"


async def test_messages_filter_by_buyer(client, ctx):
    """GET /api/messages?buyer=xxx filters by buyer."""
    await ctx.db.add_message(buyer_username="alice", body="Hello")
    await ctx.db.add_message(buyer_username="bob", body="Hi")

    resp = await client.get("/api/messages?buyer=alice")
    messages = resp.json()
    assert len(messages) == 1
    assert messages[0]["buyer_username"] == "alice"


async def test_messages_reply(client, ctx):
    """POST /api/messages/{id}/reply sends a manual reply."""
    msg_id = await ctx.db.add_message(
        buyer_username="buyer_reply",
        body="Is this authentic?",
        category="condition",
    )
    resp = await client.post(f"/api/messages/{msg_id}/reply", json={
        "body": "Yes, it is 100% authentic from Japan.",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["direction"] == "outbound"
    assert data["buyer_username"] == "buyer_reply"


async def test_messages_reply_not_found(client):
    """POST /api/messages/{id}/reply returns 404 for missing message."""
    resp = await client.post("/api/messages/99999/reply", json={
        "body": "test",
    })
    assert resp.status_code == 404


# --- エクスポート API ---


async def test_export_candidates_csv(client, ctx):
    """GET /api/export/candidates?format=csv returns CSV."""
    await ctx.db.add_candidate(
        item_code="EXP01", source_site="amazon", title_jp="エクスポートテスト",
        title_en="Export Test", cost_jpy=1000, ebay_price_usd=30.0,
        net_profit_jpy=1000, margin_rate=1.0,
    )
    resp = await client.get("/api/export/candidates?format=csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "EXP01" in resp.text


async def test_export_candidates_json(client, ctx):
    """GET /api/export/candidates?format=json returns JSON."""
    await ctx.db.add_candidate(
        item_code="EXP02", source_site="rakuten", title_jp="JSON出力テスト",
        title_en=None, cost_jpy=2000, ebay_price_usd=50.0,
        net_profit_jpy=2000, margin_rate=1.0,
    )
    resp = await client.get("/api/export/candidates?format=json")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    data = resp.json()
    assert len(data) >= 1


async def test_export_orders_csv(client, ctx):
    """GET /api/export/orders?format=csv returns CSV."""
    await ctx.db.add_order(
        ebay_order_id="EXP-ORD-001",
        buyer_username="exporter",
        sale_price_usd=80.0,
    )
    resp = await client.get("/api/export/orders?format=csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "EXP-ORD-001" in resp.text


async def test_export_invalid_type(client):
    """GET /api/export/invalid returns 400."""
    resp = await client.get("/api/export/invalid")
    assert resp.status_code == 400


async def test_export_invalid_format(client):
    """GET /api/export/candidates?format=xml returns 400."""
    resp = await client.get("/api/export/candidates?format=xml")
    assert resp.status_code == 400


# --- ジョブ実行履歴 API ---


async def test_job_runs_empty(client):
    resp = await client.get("/api/job-runs")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_job_runs_list(client, ctx):
    await ctx.db.create_job_run("research", params={"keywords": ["test"]})
    run_id = await ctx.db.create_job_run("listing")
    await ctx.db.complete_job_run(run_id, items_processed=3)

    resp = await client.get("/api/job-runs")
    assert resp.status_code == 200
    runs = resp.json()
    assert len(runs) == 2


async def test_job_runs_filter_by_name(client, ctx):
    await ctx.db.create_job_run("research")
    await ctx.db.create_job_run("listing")
    await ctx.db.create_job_run("research")

    resp = await client.get("/api/job-runs?job_name=research")
    runs = resp.json()
    assert len(runs) == 2


# --- システムヘルス API ---


async def test_system_health_empty(client):
    resp = await client.get("/api/system/health")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_system_health_with_data(client, ctx):
    await ctx.db.upsert_integration_status("ebay_api", "ok")
    await ctx.db.upsert_integration_status("deepl", "degraded", error_message="Rate limited")

    resp = await client.get("/api/system/health")
    assert resp.status_code == 200
    statuses = resp.json()
    assert len(statuses) == 2


# --- Dashboard にジョブ履歴・ヘルス追加 ---


async def test_dashboard_includes_job_runs_and_health(client, ctx):
    run_id = await ctx.db.create_job_run("research")
    await ctx.db.complete_job_run(run_id, items_processed=10)
    await ctx.db.upsert_integration_status("ebay_api", "ok")

    resp = await client.get("/api/dashboard")
    data = resp.json()
    assert "recent_jobs" in data
    assert len(data["recent_jobs"]) == 1
    assert "health" in data
    assert len(data["health"]) == 1
