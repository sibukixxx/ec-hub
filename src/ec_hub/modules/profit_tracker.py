"""利益計算・日次レポートモジュール.

仕様書 §3 に基づく純利益計算ロジック。
全ての手数料・送料・為替バッファを控除した純利益を計算する。
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

import httpx

from ec_hub.config import load_fee_rules, load_settings
from ec_hub.db import Database
from ec_hub.models import ProfitBreakdown
from ec_hub.modules.notifier import Notifier

logger = logging.getLogger(__name__)


class ProfitTracker:
    """利益計算と日次レポート生成."""

    def __init__(self, db: Database, settings: dict | None = None, fee_rules: dict | None = None) -> None:
        self._db = db
        self._settings = settings or load_settings()
        self._fee_rules = fee_rules or load_fee_rules()
        self._notifier = Notifier(self._settings)
        self._cached_fx_rate: float | None = None
        self._cached_fx_at: datetime | None = None

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _parse_timestamp(value: str | None) -> datetime | None:
        if not value:
            return None
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    @classmethod
    def _is_fresh(cls, timestamp: datetime | None, ttl_minutes: int) -> bool:
        if timestamp is None:
            return False
        return cls._now() - timestamp <= timedelta(minutes=ttl_minutes)

    @staticmethod
    def _extract_jpy_rate(payload: dict) -> float:
        for key in ("rates", "conversion_rates"):
            rates = payload.get(key)
            if isinstance(rates, dict) and "JPY" in rates:
                return float(rates["JPY"])
        raise ValueError("JPY rate not found in response payload")

    def _remember_fx_rate(self, rate: float, *, cached_at: datetime | None = None) -> float:
        self._cached_fx_rate = rate
        self._cached_fx_at = cached_at or self._now()
        return rate

    def _get_exchange_rate_urls(self) -> list[str]:
        ex_config = self._settings.get("exchange_rate", {})
        urls = [ex_config.get("base_url", "https://api.exchangerate-api.com/v4/latest/USD")]
        urls.extend(ex_config.get("fallback_urls", []))

        deduped: list[str] = []
        for url in urls:
            if url and url not in deduped:
                deduped.append(url)
        return deduped

    async def _set_exchange_rate_status(self, status: str, message: str | None = None) -> None:
        current = await self._db.get_integration_status("exchange_rate")
        if status == "degraded" and message and (current is None or current.get("status") != "degraded"):
            await self._notifier.notify_exchange_rate_warning(message)
        await self._db.upsert_integration_status(
            "exchange_rate",
            status,
            error_message=message,
        )

    async def get_fx_rate(self) -> float:
        """USD→JPYの為替レートを取得する."""
        ex_config = self._settings.get("exchange_rate", {})
        fallback = ex_config.get("fallback_rate", 150.0)
        ttl_minutes = int(ex_config.get("cache_ttl_minutes", 60))

        if self._cached_fx_rate is not None and self._is_fresh(self._cached_fx_at, ttl_minutes):
            return self._cached_fx_rate

        cached_record = await self._db.get_exchange_rate_cache()
        cached_fetched_at = self._parse_timestamp(cached_record.get("fetched_at") if cached_record else None)
        if cached_record and self._is_fresh(cached_fetched_at, ttl_minutes):
            rate = float(cached_record["rate"])
            await self._set_exchange_rate_status(
                "ok",
                f"Using cached rate {rate:.2f} from {cached_record['source']}",
            )
            return self._remember_fx_rate(rate, cached_at=cached_fetched_at)

        errors: list[str] = []
        async with httpx.AsyncClient(timeout=10.0) as client:
            for url in self._get_exchange_rate_urls():
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    rate = self._extract_jpy_rate(resp.json())
                    await self._db.upsert_exchange_rate_cache(
                        base_currency="USD",
                        quote_currency="JPY",
                        rate=rate,
                        source=url,
                        fetched_at=self._now().isoformat(),
                    )
                    await self._set_exchange_rate_status(
                        "ok",
                        f"Fetched from {url}",
                    )
                    logger.info("為替レート取得: 1 USD = %.2f JPY (%s)", rate, url)
                    return self._remember_fx_rate(rate)
                except Exception as e:
                    errors.append(f"{url}: {e}")
                    logger.warning("為替レート取得失敗 (%s): %s", url, e)

        if cached_record:
            rate = float(cached_record["rate"])
            await self._set_exchange_rate_status(
                "degraded",
                "Using last known rate "
                f"{rate:.2f} from {cached_record['source']} ({cached_record['fetched_at']})"
                + (f" after failures: {' | '.join(errors[:2])}" if errors else ""),
            )
            logger.warning("為替レート取得失敗。保存済みレートを使用: %.2f", rate)
            return self._remember_fx_rate(rate)

        await self._set_exchange_rate_status(
            "degraded",
            f"Using static fallback {fallback:.2f}" + (f" after failures: {' | '.join(errors[:2])}" if errors else ""),
        )
        logger.warning("為替レート取得失敗、固定フォールバック値を使用: %.2f", fallback)
        return self._remember_fx_rate(fallback)

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
        today_orders = [o for o in orders if o.get("ordered_at", "").startswith(date_str)]

        total_revenue = sum(int((o.get("sale_price_usd", 0) or 0) * (o.get("fx_rate", 0) or 150)) for o in today_orders)
        total_cost = sum(o.get("actual_cost_jpy", 0) or 0 for o in today_orders)
        total_profit = sum(o.get("net_profit_jpy", 0) or 0 for o in today_orders)

        candidates = await self._db.get_candidates()
        new_candidates = [c for c in candidates if c.get("created_at", "").startswith(date_str)]

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
