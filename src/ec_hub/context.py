"""Application context — dependency container."""

from __future__ import annotations

import logging
from pathlib import Path

from ec_hub.config import load_fee_rules, load_settings
from ec_hub.db import Database
from ec_hub.repositories import CandidateRepository, MessageRepository, OrderRepository

logger = logging.getLogger(__name__)


class AppContext:
    """Aggregates settings, database, and repositories."""

    def __init__(
        self,
        *,
        settings: dict,
        fee_rules: dict,
        db: Database,
    ) -> None:
        self.settings = settings
        self.fee_rules = fee_rules
        self.db = db
        self.candidates = CandidateRepository(db)
        self.orders = OrderRepository(db)
        self.messages = MessageRepository(db)

    @classmethod
    def create(
        cls,
        *,
        settings_path: Path | None = None,
        fee_rules_path: Path | None = None,
        db_path: str | Path = "db/ebay.db",
    ) -> AppContext:
        try:
            settings = load_settings(settings_path)
        except FileNotFoundError:
            logger.warning("settings.yaml not found, using empty settings")
            settings = {}
        try:
            fee_rules = load_fee_rules(fee_rules_path)
        except FileNotFoundError:
            logger.warning("fee_rules.yaml not found, using empty fee_rules")
            fee_rules = {}

        db = Database(db_path)
        return cls(settings=settings, fee_rules=fee_rules, db=db)

    async def connect(self) -> None:
        await self.db.connect()
        logger.info("AppContext connected")

    async def close(self) -> None:
        await self.db.close()
        logger.info("AppContext closed")

    async def __aenter__(self) -> AppContext:
        await self.connect()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
