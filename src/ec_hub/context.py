"""Application context — dependency container."""

from __future__ import annotations

import logging
from pathlib import Path

from ec_hub.config import load_fee_rules, load_settings
from ec_hub.config_schema import FeeRules, Settings
from ec_hub.db import Database
from ec_hub.repositories import CandidateRepository, MessageRepository, OrderRepository

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class AppContext:
    """Aggregates settings, database, and repositories."""

    def __init__(
        self,
        *,
        settings: Settings | dict,
        fee_rules: FeeRules | dict,
        db: Database,
    ) -> None:
        self.settings = settings
        self.fee_rules = fee_rules
        self.db = db
        self.candidates = CandidateRepository(db)
        self.orders = OrderRepository(db)
        self.messages = MessageRepository(db)

    _DEFAULT_DB_PATH = "db/ebay.db"

    @classmethod
    def create(
        cls,
        *,
        settings_path: Path | None = None,
        fee_rules_path: Path | None = None,
        db_path: str | Path | None = None,
        validate_services: bool = False,
    ) -> AppContext:
        try:
            settings = load_settings(settings_path)
        except FileNotFoundError:
            logger.warning("settings.yaml not found, using empty settings")
            settings = Settings()
        try:
            fee_rules = load_fee_rules(fee_rules_path)
        except FileNotFoundError:
            logger.warning("fee_rules.yaml not found, using empty fee_rules")
            fee_rules = FeeRules()

        # Resolve paths and optionally validate services
        if isinstance(settings, Settings):
            settings.resolve_paths(_PROJECT_ROOT)

            if validate_services:
                availability = settings.validate_required_services()

                for svc in availability.degraded:
                    logger.warning("Service '%s' has no API keys configured — running in degraded mode", svc)
                if availability.unavailable_required:
                    raise SystemExit(
                        f"Required service(s) not configured: "
                        f"{', '.join(availability.unavailable_required)}. "
                        "Set API keys in settings.yaml, settings.local.yaml, "
                        "or environment variables."
                    )

            # Use resolved DB path from settings only when db_path not explicitly set
            if db_path is None and settings.database.resolved_path:
                db_path = settings.database.resolved_path

        if db_path is None:
            db_path = cls._DEFAULT_DB_PATH

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
