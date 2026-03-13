"""利益計算・日次レポートモジュール.

仕様書 §3 に基づく純利益計算ロジック。
全ての手数料・送料・為替バッファを控除した純利益を計算する。
"""

from __future__ import annotations

import logging
from datetime import date, datetime

import httpx

from ec_hub.config import load_fee_rules, load_settings
from ec_hub.db import Database
from ec_hub.models import ProfitBreakdown

logger = logging.getLogger(__name__)


class ProfitTracker:
    """利益計算と日次レポート生成."""

    def __init__(self, db: Database, settings: dict | None = None, fee_rules: dict | None = None) -> None:
        self._db = db
        self._settings = settings or load_settings()
        self._fee_rules = fee_rules or load_fee_rules()
        self._cached_fx_rate: float | None = None

    async def get_fx_rate(self) -> float:
        """USD→JPYの為替レートを取得する."""
        if self._cached_fx_rate is not None:
            return self._cached_fx_rate

        ex_config = self._settings.get("exchange_rate", {})
        fallback = ex_config.get("fallback_rate", 150.0)
        base_url = ex_config.get("base_url", "https://api.exchangerate-api.com/v4/latest/USD")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(base_url)
                resp.raise_for_status()
                data = resp.json()
                rate = data.get("rates", {}).get("JPY", fallback)
                self._cached_fx_rate = float(rate)
                logger.info("為替レート取得: 1 USD = %.2f JPY", self._cached_fx_rate)
                return self._cached_fx_rate
        except Exception:
            logger.warning("為替レート取得失敗、フォールバック値を使用: %.2f", fallback)
            self._cached_fx_rate = fallback
            return fallback

    def calc_shipping(self, weight_g: int, destination: str) -> int:
        """国際送料を計算する."""
        shipping_config = self._fee_rules.get("shipping", {})
        zones = shipping_config.get("zones", {})
        dest_zones = shipping_config.get("destination_zones", {})

        zone = dest_zones.get(destination, "OTHER")
        tiers = zones.get(zone, zones.get("OTHER", []))

        for tier in tiers:
            if weight_g <= tier["max_weight_g"]:
                return tier["cost"]

        # 最重量を超えた場合は最大送料
        return tiers[-1]["cost"] if tiers else 4000

    def calc_net_profit(
        self,
        jpy_cost: int,
        ebay_price_usd: float,
        weight_g: int,
        destination: str,
        fx_rate: float,
        *,
        packing_size: str = "medium",
    ) -> ProfitBreakdown:
        """純利益を計算する（仕様書 §3.2）.

        Args:
            jpy_cost: 仕入れ価格（円）
            ebay_price_usd: eBay出品価格（ドル）
            weight_g: 重量（g）
            destination: 配送先国コード
            fx_rate: 為替レート（USD→JPY）
            packing_size: 梱包サイズ ("small", "medium", "large")

        Returns:
            ProfitBreakdown: 利益の内訳
        """
        jpy_revenue = int(ebay_price_usd * fx_rate)

        ebay_fee_rate = self._fee_rules.get("ebay_fees", {}).get("default_rate", 0.1325)
        ebay_fee = int(jpy_revenue * ebay_fee_rate)

        payoneer_rate = self._fee_rules.get("payoneer", {}).get("rate", 0.02)
        payoneer_fee = int(jpy_revenue * payoneer_rate)

        shipping_cost = self.calc_shipping(weight_g, destination)

        packing_costs = self._fee_rules.get("packing", {})
        packing_cost = packing_costs.get(packing_size, packing_costs.get("default_cost", 200))

        fx_buffer_rate = self._fee_rules.get("fx_buffer", {}).get("rate", 0.03)
        fx_buffer = int(jpy_revenue * fx_buffer_rate)

        total_cost = jpy_cost + ebay_fee + payoneer_fee + shipping_cost + packing_cost + fx_buffer
        net_profit = jpy_revenue - total_cost
        margin_rate = net_profit / jpy_cost if jpy_cost > 0 else 0.0

        return ProfitBreakdown(
            jpy_cost=jpy_cost,
            ebay_price_usd=ebay_price_usd,
            fx_rate=fx_rate,
            jpy_revenue=jpy_revenue,
            ebay_fee=ebay_fee,
            payoneer_fee=payoneer_fee,
            shipping_cost=shipping_cost,
            packing_cost=packing_cost,
            fx_buffer=fx_buffer,
            total_cost=total_cost,
            net_profit=net_profit,
            margin_rate=margin_rate,
        )

    async def generate_daily_report(self, report_date: date | None = None) -> dict:
        """日次レポートを生成してDBに保存する."""
        target_date = report_date or date.today()
        date_str = target_date.isoformat()

        orders = await self._db.get_orders()
        today_orders = [
            o for o in orders
            if o.get("ordered_at", "").startswith(date_str)
        ]

        total_revenue = sum(
            int((o.get("sale_price_usd", 0) or 0) * (o.get("fx_rate", 0) or 150))
            for o in today_orders
        )
        total_cost = sum(o.get("actual_cost_jpy", 0) or 0 for o in today_orders)
        total_profit = sum(o.get("net_profit_jpy", 0) or 0 for o in today_orders)

        candidates = await self._db.get_candidates()
        new_candidates = [
            c for c in candidates
            if c.get("created_at", "").startswith(date_str)
        ]

        report = {
            "report_date": date_str,
            "total_revenue_jpy": total_revenue,
            "total_cost_jpy": total_cost,
            "total_profit_jpy": total_profit,
            "orders_count": len(today_orders),
            "new_candidates_count": len(new_candidates),
            "new_listings_count": 0,
        }

        await self._db.save_daily_report(**report)
        logger.info("日次レポート生成: %s", date_str)
        return report
