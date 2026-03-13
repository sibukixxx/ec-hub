"""利益計算のテスト."""

import pytest

from ec_hub.db import Database
from ec_hub.modules.profit_tracker import ProfitTracker


@pytest.fixture
def fee_rules():
    return {
        "ebay_fees": {"default_rate": 0.1325},
        "payoneer": {"rate": 0.02},
        "fx_buffer": {"rate": 0.03},
        "packing": {"default_cost": 200, "small": 100, "medium": 200, "large": 300},
        "shipping": {
            "zones": {
                "US": [
                    {"max_weight_g": 500, "cost": 1500},
                    {"max_weight_g": 1000, "cost": 2000},
                    {"max_weight_g": 2000, "cost": 2800},
                ],
                "OTHER": [
                    {"max_weight_g": 500, "cost": 2000},
                    {"max_weight_g": 1000, "cost": 2500},
                ],
            },
            "destination_zones": {"US": "US", "CA": "US", "GB": "EU"},
        },
    }


@pytest.fixture
def settings():
    return {
        "exchange_rate": {"fallback_rate": 150.0},
        "database": {"path": ":memory:"},
    }


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.close()


@pytest.fixture
def tracker(db, settings, fee_rules):
    return ProfitTracker(db, settings, fee_rules)


def test_calc_shipping(tracker):
    assert tracker.calc_shipping(300, "US") == 1500
    assert tracker.calc_shipping(800, "US") == 2000
    assert tracker.calc_shipping(1500, "US") == 2800


def test_calc_shipping_unknown_zone(tracker):
    # 未知の配送先はOTHERゾーンにフォールバック
    cost = tracker.calc_shipping(300, "ZZ")
    assert cost == 2000


def test_calc_net_profit_standard(tracker):
    """仕様書 §3.3 の「現実的（標準品）」ケース."""
    breakdown = tracker.calc_net_profit(
        jpy_cost=3000,
        ebay_price_usd=80.0,
        weight_g=500,
        destination="US",
        fx_rate=150.0,
    )
    # 売上: $80 * 150 = ¥12,000
    assert breakdown.jpy_revenue == 12000
    # eBay手数料: 12000 * 0.1325 = ¥1,590
    assert breakdown.ebay_fee == 1590
    # Payoneer手数料: 12000 * 0.02 = ¥240
    assert breakdown.payoneer_fee == 240
    # 送料: 500g, US = ¥1,500
    assert breakdown.shipping_cost == 1500
    # 梱包費: ¥200
    assert breakdown.packing_cost == 200
    # 為替バッファ: 12000 * 0.03 = ¥360
    assert breakdown.fx_buffer == 360
    # 費用合計: 3000 + 1590 + 240 + 1500 + 200 + 360 = ¥6,890
    assert breakdown.total_cost == 6890
    # 純利益: 12000 - 6890 = ¥5,110
    assert breakdown.net_profit == 5110
    # 利益率: 5110 / 3000 = 170.3%
    assert breakdown.margin_rate > 1.0


def test_calc_net_profit_heavy_item(tracker):
    """重量物ケース - 送料が高くなる."""
    breakdown = tracker.calc_net_profit(
        jpy_cost=3000,
        ebay_price_usd=80.0,
        weight_g=2000,
        destination="US",
        fx_rate=150.0,
    )
    assert breakdown.shipping_cost == 2800
    assert breakdown.net_profit < 5110  # 標準品より利益が少ない


def test_calc_net_profit_margin_too_low(tracker):
    """利益率が低いケース."""
    breakdown = tracker.calc_net_profit(
        jpy_cost=10000,
        ebay_price_usd=80.0,
        weight_g=500,
        destination="US",
        fx_rate=150.0,
    )
    # 仕入れが高いので利益率は低い
    assert breakdown.margin_rate < 0.30
