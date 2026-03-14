"""Job execution wrapper with automatic history recording."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Awaitable, Callable

if TYPE_CHECKING:
    from ec_hub.db import Database

logger = logging.getLogger(__name__)


class JobRunner:
    """Wraps async job functions and records execution to job_runs table."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def run(
        self,
        job_name: str,
        fn: Callable[[], Awaitable[Any]],
        *,
        params: dict | None = None,
    ) -> Any:
        run_id = await self._db.create_job_run(job_name, params=params)
        try:
            result = await fn()
            items, warnings, errors = self._parse_result(result)
            await self._db.complete_job_run(
                run_id,
                items_processed=items,
                warnings=warnings,
                errors=errors,
            )
            return result
        except Exception as exc:
            await self._db.fail_job_run(run_id, error_message=str(exc))
            raise

    @staticmethod
    def _parse_result(result: Any) -> tuple[int, int, int]:
        if isinstance(result, tuple) and len(result) == 3:
            return (int(result[0]), int(result[1]), int(result[2]))
        if isinstance(result, int):
            return (result, 0, 0)
        return (0, 0, 0)
