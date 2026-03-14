"""Export use case."""

from __future__ import annotations

import csv
import io
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ec_hub.context import AppContext

VALID_TYPES = {"candidates", "orders"}
VALID_FORMATS = {"csv", "json"}


class ExportUseCase:
    """Data export orchestration."""

    def __init__(self, ctx: AppContext) -> None:
        self._ctx = ctx

    async def export_data(self, data_type: str, fmt: str) -> tuple[str, str]:
        """Export data and return (content, media_type)."""
        if data_type not in VALID_TYPES:
            raise ValueError(f"Invalid type. Must be one of: {VALID_TYPES}")
        if fmt not in VALID_FORMATS:
            raise ValueError(f"Invalid format. Must be one of: {VALID_FORMATS}")

        if data_type == "candidates":
            rows = await self._ctx.candidates.list(limit=10000)
        else:
            rows = await self._ctx.orders.list(limit=10000)

        if fmt == "json":
            content = json.dumps(rows, ensure_ascii=False, indent=2, default=str)
            return content, "application/json"

        # CSV
        if not rows:
            return "", "text/csv"

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue(), "text/csv"
