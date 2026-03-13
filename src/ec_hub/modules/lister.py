"""出品モジュール.

仕様書 §4.2 に基づく自動出品。
承認済み候補をeBay APIで出品する。セリングリミットを自動管理する。
"""

from __future__ import annotations

import logging

from ec_hub.config import load_settings
from ec_hub.db import Database
from ec_hub.modules.notifier import Notifier

logger = logging.getLogger(__name__)


class Lister:
    """eBay自動出品管理."""

    def __init__(self, db: Database, settings: dict | None = None) -> None:
        self._db = db
        self._settings = settings or load_settings()
        self._listing_config = self._settings.get("listing", {})
        self._notifier = Notifier(self._settings)

    @property
    def max_daily_listings(self) -> int:
        return self._listing_config.get("max_daily_listings", 10)

    @property
    def limit_warning_threshold(self) -> int:
        return self._listing_config.get("limit_warning_threshold", 3)

    async def list_candidate(self, candidate_id: int) -> bool:
        """承認済み候補をeBayに出品する.

        TODO: eBay API (Trading API / Inventory API) を使った実際の出品処理
        - 商品タイトルの英語翻訳 (DeepL API)
        - 商品説明テンプレートの適用
        - 価格設定（純利益率30%確保）
        - 送料設定
        - 画像のアップロード
        """
        candidates = await self._db.get_candidates(status="approved")
        target = next((c for c in candidates if c["id"] == candidate_id), None)
        if not target:
            logger.warning("承認済み候補が見つかりません: id=%d", candidate_id)
            return False

        # TODO: eBay API連携
        logger.info("出品処理（未実装）: %s", target.get("title_jp", ""))
        await self._db.update_candidate_status(candidate_id, "listed")
        return True

    async def check_selling_limit(self) -> dict:
        """セリングリミットの残りを確認する.

        TODO: eBay API経由で現在の出品数・金額上限を取得
        """
        # プレースホルダ
        current = 0
        max_count = 100
        remaining = max_count - current

        if remaining <= self.limit_warning_threshold:
            await self._notifier.notify_selling_limit(remaining, max_count)

        return {"current": current, "max": max_count, "remaining": remaining}

    async def run(self) -> int:
        """承認済み候補を自動出品する.

        Returns:
            出品した商品数
        """
        approved = await self._db.get_candidates(status="approved")
        listed_count = 0

        for candidate in approved[:self.max_daily_listings]:
            success = await self.list_candidate(candidate["id"])
            if success:
                listed_count += 1

        logger.info("出品完了: %d 件", listed_count)
        return listed_count
