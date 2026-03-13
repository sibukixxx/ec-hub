"""REST API のテスト."""

import pytest
from httpx import ASGITransport, AsyncClient

import ec_hub.api as api_module
from ec_hub.db import Database


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.close()


@pytest.fixture
def settings():
    return {
        "exchange_rate": {"fallback_rate": 150.0},
        "database": {"path": ":memory:"},
        "line": {},
    }


@pytest.fixture
def fee_rules():
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
async def client(db, settings, fee_rules):
    """FastAPI テストクライアント."""
    api_module._db = db
    api_module._settings = settings
    api_module._fee_rules = fee_rules
    transport = ASGITransport(app=api_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


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


async def test_candidates_crud(client, db):
    cid = await db.add_candidate(
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


async def test_candidates_invalid_status(client, db):
    cid = await db.add_candidate(
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


async def test_orders_list(client, db):
    await db.add_order(
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


async def test_dashboard_with_data(client, db):
    """データがある場合のダッシュボード."""
    await db.add_candidate(
        item_code="C1", source_site="amazon", title_jp="a",
        title_en=None, cost_jpy=1000, ebay_price_usd=30.0,
        net_profit_jpy=1000, margin_rate=1.0,
    )
    oid = await db.add_order(
        ebay_order_id="DASH-001",
        buyer_username="b",
        sale_price_usd=50.0,
    )
    await db.update_order(oid, status="completed", net_profit_jpy=3000)

    resp = await client.get("/api/dashboard")
    data = resp.json()
    assert data["candidates"]["pending"] == 1
    assert data["orders"]["completed"] == 1
    assert data["recent_profit"] == 3000
