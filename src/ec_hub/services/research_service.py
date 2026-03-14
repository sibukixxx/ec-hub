"""リサーチユースケース."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ec_hub.context import AppContext

logger = logging.getLogger(__name__)


class ResearchService:
    """リサーチ候補の管理・検索を提供する."""

    def __init__(self, ctx: AppContext) -> None:
        self._ctx = ctx

    async def get_candidates(self, status: str | None = None, limit: int = 50) -> list[dict]:
        """候補一覧を取得する."""
        return await self._ctx.db.get_candidates(status=status, limit=limit)

    async def get_candidate(self, candidate_id: int) -> dict | None:
        """IDで候補を1件取得する."""
        return await self._ctx.db.get_candidate_by_id(candidate_id)

    async def update_candidate_status(self, candidate_id: int, status: str) -> None:
        """候補のステータスを更新する."""
        await self._ctx.db.update_candidate_status(candidate_id, status)

    async def get_research_runs(self, limit: int = 20) -> list[dict]:
        """リサーチ実行履歴を取得する."""
        return await self._ctx.db.get_research_runs(limit=limit)

    async def get_research_run(self, run_id: int) -> dict | None:
        """リサーチ実行の詳細を取得する."""
        return await self._ctx.db.get_research_run(run_id)

    async def start_research(self, keywords: list[str] | None = None, pages: int = 1) -> int:
        """Create a placeholder research_run record and return its ID.

        The researcher.run() creates per-query run records internally,
        but this parent record lets the client track "a research session was started".
        """
        query = ", ".join(keywords) if keywords else "default"
        return await self._ctx.db.create_research_run(query=query, ebay_results_count=0)

    async def execute_research(self, run_id: int, keywords: list[str] | None = None, pages: int = 1) -> None:
        """Execute research in background and update the parent run record."""
        from ec_hub.modules.researcher import Researcher

        try:
            researcher = Researcher(self._ctx.db, self._ctx.settings, self._ctx.fee_rules)
            candidates_found = await researcher.run(queries=keywords, pages=pages)
            await self._ctx.db.complete_research_run(run_id, candidates_found)
            logger.info("Research run %d completed: %d candidates", run_id, candidates_found)
        except Exception:
            logger.exception("Research run %d failed", run_id)
            await self._ctx.db.complete_research_run(run_id, 0)

    async def run_research(self, queries: list[str] | None = None, pages: int = 1) -> int:
        """価格差リサーチを同期的に実行する."""
        from ec_hub.modules.researcher import Researcher

        researcher = Researcher(self._ctx.db, self._ctx.settings, self._ctx.fee_rules)
        return await researcher.run(queries, pages=pages)
