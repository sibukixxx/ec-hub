"""HealthChecker module tests."""

import pytest

from ec_hub.db import Database
from ec_hub.modules.health_checker import check_all_services


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.close()


async def test_check_all_services_with_full_config(db):
    """全サービスのAPIキーが設定されている場合、全て ok になる."""
    settings = {
        "ebay": {"app_id": "xxx", "user_token": "yyy"},
        "deepl": {"api_key": "dpl-xxx"},
        "claude": {"api_key": "sk-xxx"},
        "amazon": {"access_key": "ak", "secret_key": "sk"},
        "rakuten": {"app_id": "rak-xxx"},
        "line": {"channel_access_token": "tok", "user_id": "uid"},
    }
    results = await check_all_services(db, settings)

    assert len(results) == 6
    for r in results:
        assert r["status"] == "ok", f"{r['service_name']} should be ok"

    # DB にも書き込まれている
    stored = await db.get_all_integration_status()
    assert len(stored) == 6


async def test_check_all_services_with_empty_config(db):
    """設定が空の場合、全て unconfigured になる."""
    settings = {}
    results = await check_all_services(db, settings)

    for r in results:
        assert r["status"] == "unconfigured", f"{r['service_name']} should be unconfigured"


async def test_check_all_services_partial_config(db):
    """一部のキーのみ設定されている場合、degraded になる."""
    settings = {
        "ebay": {"app_id": "xxx", "user_token": ""},
        "deepl": {"api_key": "dpl-xxx"},
    }
    results = await check_all_services(db, settings)

    ebay = next(r for r in results if r["service_name"] == "ebay")
    assert ebay["status"] == "degraded"
    assert "user_token" in ebay["error_message"]

    deepl = next(r for r in results if r["service_name"] == "deepl")
    assert deepl["status"] == "ok"


async def test_check_updates_existing_status(db):
    """再実行で既存の integration_status が更新される."""
    settings_v1 = {"deepl": {}}
    await check_all_services(db, settings_v1)
    status_v1 = await db.get_integration_status("deepl")
    assert status_v1["status"] == "unconfigured"

    settings_v2 = {"deepl": {"api_key": "dpl-xxx"}}
    await check_all_services(db, settings_v2)
    status_v2 = await db.get_integration_status("deepl")
    assert status_v2["status"] == "ok"
