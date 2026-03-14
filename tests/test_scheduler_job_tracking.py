"""Scheduler ジョブの JobRunner 経由実行テスト.

定期実行ジョブが job_runs テーブルに記録されることを検証する。
"""

from unittest.mock import AsyncMock, patch

import pytest

from ec_hub.context import AppContext
from ec_hub.db import Database
from ec_hub.scheduler import _run_messenger, _run_order_manager, _run_profit_tracker, _run_researcher


@pytest.fixture
def test_settings():
    return {
        "exchange_rate": {"fallback_rate": 150.0},
        "database": {"path": ":memory:"},
        "line": {},
        "research": {"keywords": ["test"]},
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


async def test_run_researcher_records_job_run(ctx):
    """_run_researcher が job_runs テーブルに記録される."""
    with patch("ec_hub.modules.researcher.Researcher") as MockResearcher:
        mock_instance = AsyncMock()
        mock_instance.run = AsyncMock(return_value=3)
        MockResearcher.return_value = mock_instance

        await _run_researcher(ctx)

    runs = await ctx.db.get_job_runs(job_name="researcher")
    assert len(runs) == 1
    assert runs[0]["status"] == "completed"
    assert runs[0]["items_processed"] == 3
    assert '"trigger": "scheduled"' in runs[0]["params_json"]


async def test_run_order_manager_records_job_run(ctx):
    """_run_order_manager が job_runs テーブルに記録される."""
    with patch("ec_hub.modules.order_manager.OrderManager") as MockOM:
        mock_instance = AsyncMock()
        mock_instance.run = AsyncMock(return_value=2)
        MockOM.return_value = mock_instance

        await _run_order_manager(ctx)

    runs = await ctx.db.get_job_runs(job_name="order_manager")
    assert len(runs) == 1
    assert runs[0]["status"] == "completed"
    assert runs[0]["items_processed"] == 2


async def test_run_messenger_records_job_run(ctx):
    """_run_messenger が job_runs テーブルに記録される."""
    with patch("ec_hub.modules.messenger.Messenger") as MockMsg:
        mock_instance = AsyncMock()
        mock_instance.run = AsyncMock(return_value=5)
        MockMsg.return_value = mock_instance

        await _run_messenger(ctx)

    runs = await ctx.db.get_job_runs(job_name="messenger")
    assert len(runs) == 1
    assert runs[0]["status"] == "completed"
    assert runs[0]["items_processed"] == 5


async def test_run_profit_tracker_records_job_run(ctx):
    """_run_profit_tracker が job_runs テーブルに記録される."""
    with patch("ec_hub.modules.profit_tracker.ProfitTracker") as MockPT:
        mock_instance = AsyncMock()
        mock_instance.generate_daily_report = AsyncMock(return_value={"report_date": "2026-03-15"})
        MockPT.return_value = mock_instance

        await _run_profit_tracker(ctx)

    runs = await ctx.db.get_job_runs(job_name="profit_tracker")
    assert len(runs) == 1
    assert runs[0]["status"] == "completed"


async def test_run_researcher_records_failure(ctx):
    """_run_researcher が失敗時に job_runs に failed を記録する."""
    with patch("ec_hub.modules.researcher.Researcher") as MockResearcher:
        mock_instance = AsyncMock()
        mock_instance.run = AsyncMock(side_effect=RuntimeError("API down"))
        MockResearcher.return_value = mock_instance

        with pytest.raises(RuntimeError, match="API down"):
            await _run_researcher(ctx)

    runs = await ctx.db.get_job_runs(job_name="researcher")
    assert len(runs) == 1
    assert runs[0]["status"] == "failed"
    assert "API down" in runs[0]["error_message"]
