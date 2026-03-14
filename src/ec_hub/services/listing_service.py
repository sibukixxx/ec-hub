"""出品ユースケース."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ec_hub.modules.lister import Lister

if TYPE_CHECKING:
    from ec_hub.context import AppContext

logger = logging.getLogger(__name__)


class ListingService:
    """出品の管理を提供する."""

    def __init__(self, ctx: AppContext) -> None:
        self._ctx = ctx
        self._lister = Lister(ctx.db, ctx.settings, ctx.fee_rules)

    def calc_listing_price(self, cost_jpy: int, weight_g: int, fx_rate: float) -> float:
        """利益率30%を確保する出品価格を計算する."""
        return self._lister.calc_listing_price(cost_jpy, weight_g, fx_rate)

    async def list_candidate(self, candidate_id: int) -> bool:
        """候補をeBayに出品する."""
        return await self._lister.list_candidate(candidate_id)

    async def run_auto_listing(self) -> int:
        """承認済み候補を自動出品する."""
        return await self._lister.run()

    async def check_selling_limit(self) -> dict:
        """セリングリミットを確認する."""
        return await self._lister.check_selling_limit()

    async def close(self) -> None:
        """リソースを解放する."""
        await self._lister.close()
