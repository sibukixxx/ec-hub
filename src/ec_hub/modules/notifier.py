"""LINE通知ハブモジュール.

各モジュールからの通知をLINE Messaging API経由でプッシュ送信する。
"""

from __future__ import annotations

import logging

import httpx

from ec_hub.config import load_settings

logger = logging.getLogger(__name__)

LINE_API_URL = "https://api.line.me/v2/bot/message/push"


class Notifier:
    """LINE通知送信."""

    def __init__(self, settings: dict | None = None) -> None:
        self._settings = settings or load_settings()
        line_config = self._settings.get("line", {})
        self._token = line_config.get("channel_access_token", "")
        self._user_id = line_config.get("user_id", "")

    @property
    def is_configured(self) -> bool:
        return bool(self._token and self._user_id)

    async def send(self, message: str) -> bool:
        """LINEメッセージを送信する."""
        if not self.is_configured:
            logger.warning("LINE通知未設定。メッセージをログに出力: %s", message)
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
                logger.info("LINE通知送信成功")
                return True
        except httpx.HTTPError as e:
            logger.error("LINE通知送信失敗: %s", e)
            return False

    async def notify_candidates(self, count: int) -> bool:
        """リサーチ候補の通知."""
        return await self.send(f"[ec-hub] 本日の候補 {count} 件が見つかりました。")

    async def notify_order(self, ebay_order_id: str, price_usd: float) -> bool:
        """新規注文の通知."""
        return await self.send(
            f"[ec-hub] 新規注文!\n注文ID: {ebay_order_id}\n売価: ${price_usd:.2f}\n仕入れ・発送をお願いします。"
        )

    async def notify_selling_limit(self, remaining: int, max_count: int) -> bool:
        """セリングリミット警告通知."""
        return await self.send(
            f"[ec-hub] セリングリミット警告\n残り {remaining}/{max_count} 品\nリミット引き上げ申請を検討してください。"
        )

    async def notify_message_escalation(self, buyer: str, body: str) -> bool:
        """バイヤーメッセージのエスカレーション通知."""
        truncated = body[:200] + "..." if len(body) > 200 else body
        return await self.send(f"[ec-hub] バイヤーメッセージ（対応必要）\nFrom: {buyer}\n{truncated}")

    async def notify_scraper_warning(self, warnings: list[str]) -> bool:
        """スクレイパー警告通知."""
        msg = "[ec-hub] スクレイパー警告\n" + "\n".join(f"- {w}" for w in warnings)
        return await self.send(msg)

    async def notify_daily_report(self, report: dict) -> bool:
        """日次レポート通知."""
        return await self.send(
            f"[ec-hub] 日次レポート ({report['report_date']})\n"
            f"注文: {report['orders_count']} 件\n"
            f"売上: ¥{report['total_revenue_jpy']:,}\n"
            f"利益: ¥{report['total_profit_jpy']:,}\n"
            f"新規候補: {report['new_candidates_count']} 件"
        )
