"""Candidate repository."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ec_hub.db import Database


class CandidateRepository:
    """Candidates table access."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def get_by_id(self, candidate_id: int) -> dict | None:
        return await self._db.get_candidate_by_id(candidate_id)

    async def list(self, status: str | None = None, limit: int = 50) -> list[dict]:
        return await self._db.get_candidates(status=status, limit=limit)

    async def add(self, **kwargs: object) -> int:
        return await self._db.add_candidate(**kwargs)

    async def update_status(self, candidate_id: int, status: str) -> None:
        await self._db.update_candidate_status(candidate_id, status)

    async def count_by_status(self, status: str | None = None) -> int:
        return await self._db.count_candidates_by_status(status)
