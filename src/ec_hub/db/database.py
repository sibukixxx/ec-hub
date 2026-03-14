"""SQLite データベース管理."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_code TEXT NOT NULL,
    source_site TEXT NOT NULL DEFAULT 'amazon',
    title_jp TEXT NOT NULL,
    title_en TEXT,
    cost_jpy INTEGER NOT NULL,
    ebay_price_usd REAL NOT NULL,
    net_profit_jpy INTEGER,
    margin_rate REAL,
    weight_g INTEGER,
    category TEXT,
    ebay_sold_count_30d INTEGER DEFAULT 0,
    image_url TEXT,
    source_url TEXT,
    match_score INTEGER,
    match_reason TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ebay_order_id TEXT NOT NULL UNIQUE,
    candidate_id INTEGER REFERENCES candidates(id),
    buyer_username TEXT,
    sale_price_usd REAL NOT NULL,
    actual_cost_jpy INTEGER,
    actual_shipping_jpy INTEGER,
    packing_cost_jpy INTEGER DEFAULT 200,
    ebay_fee_jpy INTEGER,
    payoneer_fee_jpy INTEGER,
    net_profit_jpy INTEGER,
    fx_rate REAL,
    destination_country TEXT,
    tracking_number TEXT,
    status TEXT NOT NULL DEFAULT 'awaiting_purchase',
    ordered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    shipped_at DATETIME,
    delivered_at DATETIME,
    completed_at DATETIME,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ebay_message_id TEXT UNIQUE,
    order_id INTEGER REFERENCES orders(id),
    buyer_username TEXT NOT NULL,
    direction TEXT NOT NULL DEFAULT 'inbound',
    category TEXT,
    body TEXT NOT NULL,
    auto_replied INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date DATE NOT NULL UNIQUE,
    total_revenue_jpy INTEGER DEFAULT 0,
    total_cost_jpy INTEGER DEFAULT 0,
    total_profit_jpy INTEGER DEFAULT 0,
    orders_count INTEGER DEFAULT 0,
    new_candidates_count INTEGER DEFAULT 0,
    new_listings_count INTEGER DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidates(status);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_ordered_at ON orders(ordered_at);
CREATE INDEX IF NOT EXISTS idx_messages_buyer ON messages(buyer_username);
"""


class Database:
    """非同期 SQLite データベースラッパー."""

    def __init__(self, db_path: str | Path = "db/ebay.db") -> None:
        self._db_path = Path(db_path)
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA_SQL)
        await self._db.commit()
        logger.info("Database connected: %s", self._db_path)

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    async def __aenter__(self) -> Database:
        await self.connect()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._db

    # --- Candidates ---

    async def add_candidate(
        self,
        *,
        item_code: str,
        source_site: str,
        title_jp: str,
        title_en: str | None,
        cost_jpy: int,
        ebay_price_usd: float,
        net_profit_jpy: int | None,
        margin_rate: float | None,
        weight_g: int | None = None,
        category: str | None = None,
        ebay_sold_count_30d: int = 0,
        image_url: str | None = None,
        source_url: str | None = None,
        match_score: int | None = None,
        match_reason: str | None = None,
    ) -> int:
        cursor = await self.db.execute(
            """INSERT INTO candidates
            (item_code, source_site, title_jp, title_en, cost_jpy, ebay_price_usd,
             net_profit_jpy, margin_rate, weight_g, category, ebay_sold_count_30d,
             image_url, source_url, match_score, match_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                item_code, source_site, title_jp, title_en, cost_jpy, ebay_price_usd,
                net_profit_jpy, margin_rate, weight_g, category, ebay_sold_count_30d,
                image_url, source_url, match_score, match_reason,
            ),
        )
        await self.db.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    async def get_candidates(self, status: str | None = None, limit: int = 50) -> list[dict]:
        if status:
            cursor = await self.db.execute(
                "SELECT * FROM candidates WHERE status = ? ORDER BY margin_rate DESC LIMIT ?",
                (status, limit),
            )
        else:
            cursor = await self.db.execute(
                "SELECT * FROM candidates ORDER BY created_at DESC LIMIT ?", (limit,)
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def update_candidate_status(self, candidate_id: int, status: str) -> None:
        await self.db.execute(
            "UPDATE candidates SET status = ?, updated_at = ? WHERE id = ?",
            (status, datetime.utcnow().isoformat(), candidate_id),
        )
        await self.db.commit()

    # --- Orders ---

    async def add_order(
        self,
        *,
        ebay_order_id: str,
        candidate_id: int | None = None,
        buyer_username: str | None = None,
        sale_price_usd: float,
        destination_country: str | None = None,
    ) -> int:
        cursor = await self.db.execute(
            """INSERT INTO orders
            (ebay_order_id, candidate_id, buyer_username, sale_price_usd, destination_country)
            VALUES (?, ?, ?, ?, ?)""",
            (ebay_order_id, candidate_id, buyer_username, sale_price_usd, destination_country),
        )
        await self.db.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    async def get_orders(self, status: str | None = None, limit: int = 50) -> list[dict]:
        if status:
            cursor = await self.db.execute(
                "SELECT * FROM orders WHERE status = ? ORDER BY ordered_at DESC LIMIT ?",
                (status, limit),
            )
        else:
            cursor = await self.db.execute(
                "SELECT * FROM orders ORDER BY ordered_at DESC LIMIT ?", (limit,)
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def update_order(self, order_id: int, **fields: object) -> None:
        if not fields:
            return
        fields["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [order_id]
        await self.db.execute(
            f"UPDATE orders SET {set_clause} WHERE id = ?", values  # noqa: S608
        )
        await self.db.commit()

    # --- Messages ---

    async def add_message(
        self,
        *,
        buyer_username: str,
        body: str,
        direction: str = "inbound",
        ebay_message_id: str | None = None,
        order_id: int | None = None,
        category: str | None = None,
        auto_replied: bool = False,
    ) -> int:
        cursor = await self.db.execute(
            """INSERT INTO messages
            (ebay_message_id, order_id, buyer_username, direction, category, body, auto_replied)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (ebay_message_id, order_id, buyer_username, direction, category, body, int(auto_replied)),
        )
        await self.db.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    # --- Daily Reports ---

    async def save_daily_report(
        self,
        *,
        report_date: str,
        total_revenue_jpy: int,
        total_cost_jpy: int,
        total_profit_jpy: int,
        orders_count: int,
        new_candidates_count: int,
        new_listings_count: int,
    ) -> None:
        await self.db.execute(
            """INSERT OR REPLACE INTO daily_reports
            (report_date, total_revenue_jpy, total_cost_jpy, total_profit_jpy,
             orders_count, new_candidates_count, new_listings_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                report_date, total_revenue_jpy, total_cost_jpy, total_profit_jpy,
                orders_count, new_candidates_count, new_listings_count,
            ),
        )
        await self.db.commit()
