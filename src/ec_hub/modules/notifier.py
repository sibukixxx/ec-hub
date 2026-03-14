"""LINE通知ハブモジュール.

各モジュールからの通知をLINE Messaging API経由でプッシュ送信する。
severity レベルと重複抑止 (dedupe) を備える。
"""

from __future__ import annotations

import hashlib
import logging
import time
from enum import Enum

import httpx

from ec_hub.config import load_settings

logger = logging.getLogger(__name__)

LINE_API_URL = "https://api.line.me/v2/bot/message/push"

# デフォルトの重複抑止間隔 (秒)
DEFAULT_DEDUPE_WINDOW = 3600  # 1 hour


class Severity(str, Enum):
    """通知の重大度レベル."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Notifier:
    """LINE通知送信 (severity + dedupe 対応)."""

    def __init__(
        self,
        settings: dict | None = None,
        *,
        dedupe_window: int = DEFAULT_DEDUPE_WINDOW,
        min_severity: Severity = Severity.WARNING,
    ) -> None:
        self._settings = settings or load_settings()
        line_config = self._settings.get("line", {})
        self._token = line_config.get("channel_access_token", "")
        self._user_id = line_config.get("user_id", "")
        self._dedupe_window = dedupe_window
        self._min_severity = min_severity
        # In-memory dedupe cache: {message_hash: last_sent_timestamp}
        self._sent_cache: dict[str, float] = {}

    @property
    def is_configured(self) -> bool:
        return bool(self._token and self._user_id)

    @property
    def min_severity(self) -> Severity:
        return self._min_severity

    @min_severity.setter
    def min_severity(self, value: Severity) -> None:
        self._min_severity = value

    def _severity_rank(self, severity: Severity) -> int:
        return {Severity.INFO: 0, Severity.WARNING: 1, Severity.CRITICAL: 2}[severity]

    def _should_send(self, message: str, severity: Severity) -> bool:
        """severity フィルタと dedupe チェック."""
        if self._severity_rank(severity) < self._severity_rank(self._min_severity):
            logger.debug("通知スキップ (severity %s < min %s): %s", severity, self._min_severity, message[:50])
            return False

        msg_hash = hashlib.sha256(message.encode()).hexdigest()[:16]
        now = time.monotonic()
        last_sent = self._sent_cache.get(msg_hash)
        if last_sent is not None and (now - last_sent) < self._dedupe_window:
            logger.debug("通知スキップ (dedupe window内): %s", message[:50])
            return False

        return True

    def _record_sent(self, message: str) -> None:
        """送信済みメッセージを記録."""
        msg_hash = hashlib.sha256(message.encode()).hexdigest()[:16]
        now = time.monotonic()
        self._sent_cache[msg_hash] = now

        # 古いエントリを掃除 (キャッシュ肥大防止)
        expired = [k for k, v in self._sent_cache.items() if (now - v) > self._dedupe_window * 2]
        for k in expired:
            del self._sent_cache[k]

    async def send(self, message: str, *, severity: Severity = Severity.WARNING) -> bool:
        """LINEメッセージを送信する (severity + dedupe 付き)."""
        if not self.is_configured:
            logger.warning("LINE通知未設定。メッセージをログに出力: %s", message)
            return False

        if not self._should_send(message, severity):
            return False

        payload = {
            "to": self._user_id,
            "messages": [{"type": "text", "text": message}],
        }
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(LINE_API_URL, json=payload, headers=headers)
                resp.raise_for_status()
                self._record_sent(message)
                logger.info("LINE通知送信成功 [%s]", severity.value)
                return True
        except httpx.HTTPError as e:
            logger.error("LINE通知送信失敗: %s", e)
            return False

    # --- 便利メソッド (後方互換) ---

    async def notify_candidates(self, count: int) -> bool:
        """リサーチ候補の通知."""
        return await self.send(
            f"[ec-hub] 本日の候補 {count} 件が見つかりました。",
            severity=Severity.INFO,
        )

    async def notify_order(self, ebay_order_id: str, price_usd: float) -> bool:
        """新規注文の通知."""
        return await self.send(
            f"[ec-hub] 新規注文!\n注文ID: {ebay_order_id}\n売価: ${price_usd:.2f}\n仕入れ・発送をお願いします。",
            severity=Severity.CRITICAL,
        )

    async def notify_selling_limit(self, remaining: int, max_count: int) -> bool:
        """セリングリミット警告通知."""
        return await self.send(
            f"[ec-hub] セリングリミット警告\n残り {remaining}/{max_count} 品\nリミット引き上げ申請を検討してください。",
            severity=Severity.WARNING,
        )

    async def notify_message_escalation(self, buyer: str, body: str) -> bool:
        """バイヤーメッセージのエスカレーション通知."""
        truncated = body[:200] + "..." if len(body) > 200 else body
        return await self.send(
            f"[ec-hub] バイヤーメッセージ（対応必要）\nFrom: {buyer}\n{truncated}",
            severity=Severity.CRITICAL,
        )

    async def notify_scraper_warning(self, warnings: list[str]) -> bool:
        """スクレイパー警告通知."""
        msg = "[ec-hub] スクレイパー警告\n" + "\n".join(f"- {w}" for w in warnings)
        return await self.send(msg, severity=Severity.WARNING)

    async def notify_daily_report(self, report: dict) -> bool:
        """日次レポート通知."""
        return await self.send(
            f"[ec-hub] 日次レポート ({report['report_date']})\n"
            f"注文: {report['orders_count']} 件\n"
            f"売上: ¥{report['total_revenue_jpy']:,}\n"
            f"利益: ¥{report['total_profit_jpy']:,}\n"
            f"新規候補: {report['new_candidates_count']} 件",
            severity=Severity.INFO,
        )

    async def notify_exchange_rate_warning(self, message: str) -> bool:
        """為替レート劣化時の警告通知."""
        return await self.send(
            f"[ec-hub] 為替レート警告\n{message}",
            severity=Severity.WARNING,
        )

    async def notify_job_failure(self, job_name: str, error: str) -> bool:
        """ジョブ実行失敗の通知."""
        return await self.send(
            f"[ec-hub] ジョブ実行失敗\nジョブ: {job_name}\nエラー: {error[:200]}",
            severity=Severity.CRITICAL,
        )

    async def notify_service_degraded(self, service_name: str, error: str) -> bool:
        """外部サービス劣化の通知."""
        return await self.send(
            f"[ec-hub] サービス劣化\nサービス: {service_name}\n{error[:200]}",
            severity=Severity.WARNING,
        )
