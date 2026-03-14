"""JobRunner wrapper tests."""

import pytest

from ec_hub.db import Database
from ec_hub.modules.job_runner import JobRunner


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.close()


async def test_run_records_success(db):
    async def my_job():
        return 5

    runner = JobRunner(db)
    result = await runner.run("research", my_job)
    assert result == 5

    runs = await db.get_job_runs(job_name="research")
    assert len(runs) == 1
    assert runs[0]["status"] == "completed"
    assert runs[0]["items_processed"] == 5


async def test_run_records_failure(db):
    async def failing_job():
        raise RuntimeError("Something broke")

    runner = JobRunner(db)
    with pytest.raises(RuntimeError, match="Something broke"):
        await runner.run("listing", failing_job)

    runs = await db.get_job_runs(job_name="listing")
    assert len(runs) == 1
    assert runs[0]["status"] == "failed"
    assert "Something broke" in runs[0]["error_message"]


async def test_run_stores_params(db):
    async def my_job():
        return 0

    runner = JobRunner(db)
    await runner.run("research", my_job, params={"keywords": ["anime"]})

    runs = await db.get_job_runs(job_name="research")
    assert runs[0]["params_json"] is not None
    assert "anime" in runs[0]["params_json"]


async def test_run_returns_tuple_with_warnings_and_errors(db):
    """JobRunner accepts (items, warnings, errors) tuple return."""

    async def job_with_warnings():
        return (10, 2, 1)

    runner = JobRunner(db)
    result = await runner.run("order_check", job_with_warnings)
    assert result == (10, 2, 1)

    runs = await db.get_job_runs(job_name="order_check")
    assert runs[0]["items_processed"] == 10
    assert runs[0]["warnings"] == 2
    assert runs[0]["errors"] == 1
