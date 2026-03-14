"""アプリケーション依存性コンテナ."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from ec_hub.config import load_fee_rules, load_settings
from ec_hub.db import Database

logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    """Application dependency container.

    設定・DB・外部クライアントの生成を集約し、
    API / CLI / Scheduler から共通利用する。
    """

    settings: dict = field(default_factory=dict)
    fee_rules: dict = field(default_factory=dict)
    db: Database = field(default=None)  # type: ignore[assignment]

    @classmethod
    async def create(
        cls,
        *,
        settings: dict | None = None,
        fee_rules: dict | None = None,
        db_path: str | Path | None = None,
    ) -> AppContext:
        """AppContext を生成し、DBに接続する."""
        s = settings or load_settings()
        f = fee_rules or load_fee_rules()
        path = db_path or s.get("database", {}).get("path", "db/ebay.db")
        db = Database(path)
        await db.connect()
        ctx = cls(settings=s, fee_rules=f, db=db)
        logger.info("AppContext created, DB connected")
        return ctx

    async def close(self) -> None:
        """リソースを解放する."""
        if self.db:
            await self.db.close()

    async def __aenter__(self) -> AppContext:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
