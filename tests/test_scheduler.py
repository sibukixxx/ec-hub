"""APScheduler 初期化・統合のテスト."""

import pytest
from httpx import ASGITransport, AsyncClient

from ec_hub.api import app, get_ctx
from ec_hub.context import AppContext
from ec_hub.db import Database
from ec_hub.scheduler import Scheduler


@pytest.fixture
def test_settings():
    return {
        "exchange_rate": {"fallback_rate": 150.0},
        "database": {"path": ":memory:"},
        "line": {},
        "scheduler": {
            "researcher": {"cron": "0 6,18 * * *"},
            "order_manager": {"interval_minutes": 30},
            "messenger": {"interval_minutes": 15},
            "profit_tracker": {"cron": "0 7 * * *"},
        },
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


@pytest.fixture
async def client(ctx):
    app.dependency_overrides[get_ctx] = lambda: ctx
    scheduler = Scheduler(ctx)
    app.state.scheduler = scheduler
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    app.state.scheduler = None


# --- Scheduler unit tests ---


class TestSchedulerInit:
    """Scheduler の初期化テスト."""

    def test_creates_scheduler_with_settings(self, ctx):
        """settings から Scheduler を作成できる."""
        scheduler = Scheduler(ctx)
        assert scheduler is not None
        assert not scheduler.is_running

    def test_registers_jobs_from_settings(self, ctx):
        """settings.yaml のスケジュール設定からジョブが登録される."""
        scheduler = Scheduler(ctx)
        job_names = scheduler.get_job_names()
        assert "researcher" in job_names
        assert "order_manager" in job_names
        assert "messenger" in job_names
        assert "profit_tracker" in job_names

    def test_no_scheduler_config_registers_no_jobs(self, test_fee_rules):
        """scheduler 設定がない場合はジョブが登録されない."""
        settings = {"database": {"path": ":memory:"}}
        db = Database(":memory:")
        ctx = AppContext(settings=settings, fee_rules=test_fee_rules, db=db)
        scheduler = Scheduler(ctx)
        assert scheduler.get_job_names() == []


class TestSchedulerStartStop:
    """Scheduler の起動・停止テスト."""

    @pytest.mark.asyncio
    async def test_start_and_stop(self, ctx):
        """スケジューラの起動と停止ができる."""
        scheduler = Scheduler(ctx)
        scheduler.start()
        assert scheduler.is_running
        scheduler.shutdown()
        assert not scheduler.is_running

    def test_shutdown_when_not_running_is_safe(self, ctx):
        """未起動の状態で shutdown しても例外にならない."""
        scheduler = Scheduler(ctx)
        scheduler.shutdown()  # should not raise


class TestSchedulerStatus:
    """Scheduler のステータス取得テスト."""

    @pytest.mark.asyncio
    async def test_get_status_returns_job_info(self, ctx):
        """get_status() がジョブ情報を含むステータスを返す."""
        scheduler = Scheduler(ctx)
        status = scheduler.get_status()
        assert "running" in status
        assert "jobs" in status
        assert isinstance(status["jobs"], list)
        assert len(status["jobs"]) == 4

    @pytest.mark.asyncio
    async def test_status_contains_job_details(self, ctx):
        """各ジョブのステータスに名前とトリガー情報が含まれる."""
        scheduler = Scheduler(ctx)
        status = scheduler.get_status()
        job_names = [j["name"] for j in status["jobs"]]
        assert "researcher" in job_names
        for job in status["jobs"]:
            assert "name" in job
            assert "trigger" in job


class TestSchedulerTrigger:
    """ジョブの手動トリガーテスト."""

    @pytest.mark.asyncio
    async def test_trigger_known_job(self, ctx):
        """既知のジョブ名を手動トリガーできる."""
        scheduler = Scheduler(ctx)
        result = await scheduler.trigger_job("researcher")
        assert result["job"] == "researcher"
        assert result["status"] == "triggered"

    @pytest.mark.asyncio
    async def test_trigger_unknown_job_raises(self, ctx):
        """未知のジョブ名をトリガーすると ValueError."""
        scheduler = Scheduler(ctx)
        with pytest.raises(ValueError, match="unknown_job"):
            await scheduler.trigger_job("unknown_job")


# --- API endpoint tests ---


class TestSchedulerAPI:
    """Scheduler API エンドポイントのテスト."""

    @pytest.mark.asyncio
    async def test_get_scheduler_status(self, client):
        """GET /api/scheduler/status がステータスを返す."""
        resp = await client.get("/api/scheduler/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "running" in data
        assert "jobs" in data

    @pytest.mark.asyncio
    async def test_trigger_job_success(self, client):
        """POST /api/scheduler/trigger/{job_name} が成功する."""
        resp = await client.post("/api/scheduler/trigger/researcher")
        assert resp.status_code == 200
        data = resp.json()
        assert data["job"] == "researcher"
        assert data["status"] == "triggered"

    @pytest.mark.asyncio
    async def test_trigger_unknown_job_returns_404(self, client):
        """存在しないジョブ名のトリガーは 404 を返す."""
        resp = await client.post("/api/scheduler/trigger/nonexistent")
        assert resp.status_code == 404
