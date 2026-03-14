"""APScheduler の初期化・統合モジュール.

settings.yaml のスケジュール設定を読み込み、
Researcher / OrderManager / Messenger / ProfitTracker の定期実行を管理する。
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

if TYPE_CHECKING:
    from ec_hub.context import AppContext

logger = logging.getLogger(__name__)


async def _run_researcher(ctx: AppContext) -> None:
    """Researcher の定期実行ジョブ."""
    from ec_hub.modules.researcher import Researcher

    researcher = Researcher(ctx.db, ctx.settings, ctx.fee_rules)
    count = await researcher.run()
    logger.info("Researcher 定期実行完了: %d 件登録", count)


async def _run_order_manager(ctx: AppContext) -> None:
    """OrderManager の定期実行ジョブ."""
    from ec_hub.modules.order_manager import OrderManager

    manager = OrderManager(ctx.db, ctx.settings, ctx.fee_rules)
    count = await manager.run()
    logger.info("OrderManager 定期実行完了: %d 件処理", count)


async def _run_messenger(ctx: AppContext) -> None:
    """Messenger の定期実行ジョブ."""
    from ec_hub.modules.messenger import Messenger

    messenger = Messenger(ctx.db, ctx.settings)
    count = await messenger.run()
    logger.info("Messenger 定期実行完了: %d 件処理", count)


async def _run_profit_tracker(ctx: AppContext) -> None:
    """ProfitTracker の定期実行ジョブ."""
    from ec_hub.modules.profit_tracker import ProfitTracker

    tracker = ProfitTracker(ctx.db, ctx.settings, ctx.fee_rules)
    report = await tracker.generate_daily_report()
    logger.info("ProfitTracker 日次レポート生成完了: %s", report.get("report_date"))


# ジョブ名と実行関数のマッピング
_JOB_FUNCS = {
    "researcher": _run_researcher,
    "order_manager": _run_order_manager,
    "messenger": _run_messenger,
    "profit_tracker": _run_profit_tracker,
}


def _parse_cron(cron_expr: str) -> CronTrigger:
    """cron 式を CronTrigger に変換する.

    標準5フィールド形式: minute hour day month day_of_week
    """
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {cron_expr}")
    minute, hour, day, month, day_of_week = parts
    return CronTrigger(
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
    )


class Scheduler:
    """APScheduler ベースのジョブスケジューラ."""

    def __init__(self, ctx: AppContext) -> None:
        self._ctx = ctx
        self._scheduler = AsyncIOScheduler()
        self._job_configs: dict[str, dict] = {}
        self._started = False
        self._register_jobs()

    def _register_jobs(self) -> None:
        """settings のスケジュール設定からジョブを登録する."""
        scheduler_config = self._ctx.settings.get("scheduler", {})
        if not scheduler_config:
            return

        for job_name, config in scheduler_config.items():
            if job_name not in _JOB_FUNCS:
                logger.warning("未知のジョブ名: %s", job_name)
                continue

            func = _JOB_FUNCS[job_name]
            cron_expr = config.get("cron")
            interval_minutes = config.get("interval_minutes")

            if cron_expr:
                trigger = _parse_cron(cron_expr)
                trigger_desc = f"cron: {cron_expr}"
            elif interval_minutes is not None:
                trigger = IntervalTrigger(minutes=interval_minutes)
                trigger_desc = f"interval: {interval_minutes}min"
            else:
                logger.warning("ジョブ %s にトリガー設定がありません", job_name)
                continue

            self._scheduler.add_job(
                func,
                trigger=trigger,
                id=job_name,
                name=job_name,
                args=[self._ctx],
                replace_existing=True,
            )
            self._job_configs[job_name] = {"trigger": trigger_desc}
            logger.info("ジョブ登録: %s (%s)", job_name, trigger_desc)

    @property
    def is_running(self) -> bool:
        return self._started

    def get_job_names(self) -> list[str]:
        """登録済みジョブ名の一覧を返す."""
        return [job.id for job in self._scheduler.get_jobs()]

    def start(self) -> None:
        """スケジューラを起動する."""
        if not self._started:
            self._scheduler.start()
            self._started = True
            logger.info("スケジューラ起動")

    def shutdown(self) -> None:
        """スケジューラを停止する."""
        if self._started:
            self._scheduler.shutdown(wait=False)
            self._started = False
            logger.info("スケジューラ停止")

    def get_status(self) -> dict:
        """スケジューラのステータスを返す."""
        jobs = []
        for job in self._scheduler.get_jobs():
            next_run = getattr(job, "next_run_time", None)
            job_info: dict = {
                "name": job.id,
                "trigger": self._job_configs.get(job.id, {}).get("trigger", "unknown"),
                "next_run": str(next_run) if next_run else None,
            }
            jobs.append(job_info)
        return {
            "running": self.is_running,
            "jobs": jobs,
        }

    async def trigger_job(self, job_name: str) -> dict:
        """ジョブを手動でトリガーする."""
        if job_name not in _JOB_FUNCS:
            raise ValueError(f"Unknown job: {job_name}")

        func = _JOB_FUNCS[job_name]
        # 非同期でジョブを実行（バックグラウンドタスク）
        asyncio.create_task(func(self._ctx))
        logger.info("ジョブ手動トリガー: %s", job_name)
        return {"job": job_name, "status": "triggered"}
