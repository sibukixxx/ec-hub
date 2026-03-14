"""Research use case."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ec_hub.modules.researcher import Researcher

if TYPE_CHECKING:
    from ec_hub.context import AppContext


class ResearchUseCase:
    """Research orchestration."""

    def __init__(self, ctx: AppContext) -> None:
        self._ctx = ctx

    async def run(self, keywords: list[str] | None = None, pages: int = 1) -> int:
        researcher = Researcher(self._ctx.db, self._ctx.settings, self._ctx.fee_rules)
        return await researcher.run(queries=keywords, pages=pages)
