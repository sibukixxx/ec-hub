"""SQLite データベース管理."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS research_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    ebay_results_count INTEGER NOT NULL DEFAULT 0,
    candidates_found INTEGER NOT NULL DEFAULT 0,
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
);

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
    ebay_item_id TEXT,
    ebay_title TEXT,
    ebay_url TEXT,
    research_run_id INTEGER REFERENCES research_runs(id),
    status TEXT NOT NULL DEFAULT 'pending',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL REFERENCES candidates(id),
    sku TEXT NOT NULL UNIQUE,
    offer_id TEXT,
    listing_id TEXT,
    title_en TEXT NOT NULL,
    description_html TEXT,
    listed_price_usd REAL NOT NULL,
    listed_fx_rate REAL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ebay_order_id TEXT NOT NULL UNIQUE,
    candidate_id INTEGER REFERENCES candidates(id),
    listing_id INTEGER REFERENCES listings(id),
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
    listing_id INTEGER REFERENCES listings(id),
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

CREATE UNIQUE INDEX IF NOT EXISTS idx_candidates_dedup
    ON candidates(source_site, item_code, ebay_item_id)
    WHERE ebay_item_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidates(status);
CREATE INDEX IF NOT EXISTS idx_candidates_research_run ON candidates(research_run_id);
CREATE INDEX IF NOT EXISTS idx_listings_candidate ON listings(candidate_id);
CREATE INDEX IF NOT EXISTS idx_listings_status ON listings(status);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_ordered_at ON orders(ordered_at);
CREATE INDEX IF NOT EXISTS idx_orders_listing ON orders(listing_id);
CREATE INDEX IF NOT EXISTS idx_messages_buyer ON messages(buyer_username);
CREATE INDEX IF NOT EXISTS idx_messages_listing ON messages(listing_id);
"""


_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class Database:
    """非同期 SQLite データベースラッパー."""

    def __init__(self, db_path: str | Path = "db/ebay.db") -> None:
        path = Path(db_path)
        # Resolve relative paths against project root (not cwd)
        if str(db_path) != ":memory:" and not path.is_absolute():
            path = _PROJECT_ROOT / path
        self._db_path = path
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        if str(self._db_path) != ":memory:":
            parent = self._db_path.parent
            parent.mkdir(parents=True, exist_ok=True)
            if not os.access(parent, os.W_OK):
                raise PermissionError(
                    f"No write permission on database directory: {parent}"
                )
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

    # --- Research Runs ---

    async def create_research_run(
        self,
        *,
        query: str,
        ebay_results_count: int = 0,
    ) -> int:
        cursor = await self.db.execute(
            "INSERT INTO research_runs (query, ebay_results_count) VALUES (?, ?)",
            (query, ebay_results_count),
        )
        await self.db.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    async def complete_research_run(
        self, run_id: int, candidates_found: int
    ) -> None:
        await self.db.execute(
            """UPDATE research_runs
            SET candidates_found = ?, completed_at = CURRENT_TIMESTAMP
            WHERE id = ?""",
            (candidates_found, run_id),
        )
        await self.db.commit()

    async def get_research_run(self, run_id: int) -> dict | None:
        cursor = await self.db.execute(
            "SELECT * FROM research_runs WHERE id = ?", (run_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_research_runs(self, limit: int = 20) -> list[dict]:
        cursor = await self.db.execute(
            "SELECT * FROM research_runs ORDER BY id DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

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
        ebay_item_id: str | None = None,
        ebay_title: str | None = None,
        ebay_url: str | None = None,
        research_run_id: int | None = None,
    ) -> int:
        # Upsert when ebay_item_id is provided: update prices but preserve status
        if ebay_item_id is not None:
            cursor = await self.db.execute(
                """SELECT id FROM candidates
                WHERE source_site = ? AND item_code = ? AND ebay_item_id = ?""",
                (source_site, item_code, ebay_item_id),
            )
            existing = await cursor.fetchone()
            if existing:
                await self.db.execute(
                    """UPDATE candidates SET
                        cost_jpy = ?, ebay_price_usd = ?, net_profit_jpy = ?,
                        margin_rate = ?, weight_g = ?, category = ?,
                        ebay_sold_count_30d = ?, image_url = ?, source_url = ?,
                        ebay_title = ?, ebay_url = ?, research_run_id = ?,
                        updated_at = ?
                    WHERE id = ?""",
                    (
                        cost_jpy, ebay_price_usd, net_profit_jpy,
                        margin_rate, weight_g, category,
                        ebay_sold_count_30d, image_url, source_url,
                        ebay_title, ebay_url, research_run_id,
                        datetime.utcnow().isoformat(), existing["id"],
                    ),
                )
                await self.db.commit()
                return existing["id"]

        cursor = await self.db.execute(
            """INSERT INTO candidates
            (item_code, source_site, title_jp, title_en, cost_jpy, ebay_price_usd,
             net_profit_jpy, margin_rate, weight_g, category, ebay_sold_count_30d,
             image_url, source_url, match_score, match_reason,
             ebay_item_id, ebay_title, ebay_url, research_run_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                item_code, source_site, title_jp, title_en, cost_jpy, ebay_price_usd,
                net_profit_jpy, margin_rate, weight_g, category, ebay_sold_count_30d,
                image_url, source_url, match_score, match_reason,
                ebay_item_id, ebay_title, ebay_url, research_run_id,
            ),
        )
        await self.db.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    async def upsert_candidate(
        self,
        *,
        item_code: str,
        source_site: str,
        ebay_item_id: str,
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
        ebay_title: str | None = None,
        ebay_url: str | None = None,
        research_run_id: int | None = None,
    ) -> int:
        """候補を登録または更新する (重複排除).

        source_site + item_code + ebay_item_id の組み合わせで既存行を検索し、
        存在すれば価格情報を更新、なければ新規挿入する。
        """
        cursor = await self.db.execute(
            """SELECT id FROM candidates
            WHERE source_site = ? AND item_code = ? AND ebay_item_id = ?""",
            (source_site, item_code, ebay_item_id),
        )
        existing = await cursor.fetchone()

        if existing:
            candidate_id = existing["id"]
            await self.db.execute(
                """UPDATE candidates SET
                    cost_jpy = ?, ebay_price_usd = ?, net_profit_jpy = ?,
                    margin_rate = ?, weight_g = ?, match_score = ?, match_reason = ?,
                    ebay_title = ?, ebay_url = ?, research_run_id = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?""",
                (
                    cost_jpy, ebay_price_usd, net_profit_jpy, margin_rate,
                    weight_g, match_score, match_reason,
                    ebay_title, ebay_url, research_run_id,
                    candidate_id,
                ),
            )
            await self.db.commit()
            return candidate_id

        return await self.add_candidate(
            item_code=item_code,
            source_site=source_site,
            title_jp=title_jp,
            title_en=title_en,
            cost_jpy=cost_jpy,
            ebay_price_usd=ebay_price_usd,
            net_profit_jpy=net_profit_jpy,
            margin_rate=margin_rate,
            weight_g=weight_g,
            category=category,
            ebay_sold_count_30d=ebay_sold_count_30d,
            image_url=image_url,
            source_url=source_url,
            match_score=match_score,
            match_reason=match_reason,
            ebay_item_id=ebay_item_id,
            ebay_title=ebay_title,
            ebay_url=ebay_url,
            research_run_id=research_run_id,
        )

    async def get_candidate_by_id(self, candidate_id: int) -> dict | None:
        """IDで候補を1件取得する."""
        cursor = await self.db.execute(
            "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

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

    async def count_candidates_by_status(self, status: str | None = None) -> int:
        if status:
            cursor = await self.db.execute(
                "SELECT COUNT(*) FROM candidates WHERE status = ?", (status,)
            )
        else:
            cursor = await self.db.execute("SELECT COUNT(*) FROM candidates")
        row = await cursor.fetchone()
        return row[0]
    async def update_candidate_status(self, candidate_id: int, status: str) -> None:
        await self.db.execute(
            "UPDATE candidates SET status = ?, updated_at = ? WHERE id = ?",
            (status, datetime.utcnow().isoformat(), candidate_id),
        )
        await self.db.commit()

    # --- Listings ---

    async def add_listing(
        self,
        *,
        candidate_id: int,
        sku: str,
        title_en: str,
        listed_price_usd: float,
        listed_fx_rate: float | None = None,
        offer_id: str | None = None,
        listing_id: str | None = None,
        description_html: str | None = None,
        status: str = "active",
    ) -> int:
        cursor = await self.db.execute(
            """INSERT INTO listings
            (candidate_id, sku, offer_id, listing_id, title_en, description_html,
             listed_price_usd, listed_fx_rate, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                candidate_id, sku, offer_id, listing_id, title_en,
                description_html, listed_price_usd, listed_fx_rate, status,
            ),
        )
        await self.db.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    async def get_listing_by_id(self, listing_id: int) -> dict | None:
        cursor = await self.db.execute(
            "SELECT * FROM listings WHERE id = ?", (listing_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_listing_by_sku(self, sku: str) -> dict | None:
        cursor = await self.db.execute(
            "SELECT * FROM listings WHERE sku = ?", (sku,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def update_listing(self, id_: int, **fields: object) -> None:
        if not fields:
            return
        fields["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [id_]
        await self.db.execute(
            f"UPDATE listings SET {set_clause} WHERE id = ?", values  # noqa: S608
        )
        await self.db.commit()

    # --- Orders ---

    async def add_order(
        self,
        *,
        ebay_order_id: str,
        candidate_id: int | None = None,
        listing_id: int | None = None,
        buyer_username: str | None = None,
        sale_price_usd: float,
        destination_country: str | None = None,
    ) -> int:
        cursor = await self.db.execute(
            """INSERT INTO orders
            (ebay_order_id, candidate_id, listing_id, buyer_username, sale_price_usd, destination_country)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (ebay_order_id, candidate_id, listing_id, buyer_username, sale_price_usd, destination_country),
        )
        await self.db.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    async def get_order_by_id(self, order_id: int) -> dict | None:
        """IDで注文を1件取得する."""
        cursor = await self.db.execute(
            "SELECT * FROM orders WHERE id = ?", (order_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

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

    async def count_orders_by_status(self, status: str | None = None) -> int:
        if status:
            cursor = await self.db.execute(
                "SELECT COUNT(*) FROM orders WHERE status = ?", (status,)
            )
        else:
            cursor = await self.db.execute("SELECT COUNT(*) FROM orders")
        row = await cursor.fetchone()
        return row[0]

    async def get_total_completed_profit(self) -> int:
        """完了済み注文の合計利益を取得する."""
        cursor = await self.db.execute(
            "SELECT COALESCE(SUM(net_profit_jpy), 0) as total FROM orders WHERE status = 'completed'"
        )
        row = await cursor.fetchone()
        return int(row["total"])
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
        listing_id: int | None = None,
        category: str | None = None,
        auto_replied: bool = False,
    ) -> int:
        cursor = await self.db.execute(
            """INSERT INTO messages
            (ebay_message_id, order_id, listing_id, buyer_username, direction, category, body, auto_replied)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (ebay_message_id, order_id, listing_id, buyer_username, direction, category, body, int(auto_replied)),
        )
        await self.db.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    async def get_messages(
        self, buyer_username: str | None = None, limit: int = 50
    ) -> list[dict]:
        if buyer_username:
            cursor = await self.db.execute(
                "SELECT * FROM messages WHERE buyer_username = ? ORDER BY created_at DESC LIMIT ?",
                (buyer_username, limit),
            )
        else:
            cursor = await self.db.execute(
                "SELECT * FROM messages ORDER BY created_at DESC LIMIT ?", (limit,)
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_message_by_id(self, message_id: int) -> dict | None:
        cursor = await self.db.execute("SELECT * FROM messages WHERE id = ?", (message_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

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
