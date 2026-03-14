"""Listing use case."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ec_hub.modules.lister import Lister

if TYPE_CHECKING:
    from ec_hub.context import AppContext


class ListingUseCase:
    """eBay listing orchestration."""

    def __init__(self, ctx: AppContext) -> None:
        self._ctx = ctx

    async def run(self) -> int:
        lister = Lister(self._ctx.db, self._ctx.settings, self._ctx.fee_rules)
        try:
            return await lister.run()
        finally:
            await lister.close()

    async def check_selling_limit(self) -> dict:
        lister = Lister(self._ctx.db, self._ctx.settings, self._ctx.fee_rules)
        try:
            return await lister.check_selling_limit()
        finally:
            await lister.close()
