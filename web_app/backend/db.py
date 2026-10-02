"""
SQLite storage for paper-trading balances, orders and trades.
"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import List, Dict, Any, Optional

DB_PATH = Path(__file__).resolve().parent / "paper_trading.db"


def _connect():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS balances (
                asset   TEXT PRIMARY KEY,
                free    REAL NOT NULL DEFAULT 0,
                locked  REAL NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS orders (
                id          TEXT PRIMARY KEY,
                symbol      TEXT NOT NULL,
                side        TEXT NOT NULL,
                type        TEXT NOT NULL,
                price       REAL,
                amount      REAL NOT NULL,
                filled      REAL NOT NULL DEFAULT 0,
                status      TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS trades (
                id          TEXT PRIMARY KEY,
                order_id    TEXT NOT NULL,
                symbol      TEXT NOT NULL,
                side        TEXT NOT NULL,
                price       REAL NOT NULL,
                amount      REAL NOT NULL,
                created_at  TEXT NOT NULL
            );
            """
        )

        # Seed default paper balances if empty
        row = conn.execute("SELECT COUNT(*) AS c FROM balances").fetchone()
        if row["c"] == 0:
            defaults = [
                ("USDT", 10_000.0, 0.0),
                ("BTC", 0.15, 0.0),
                ("ETH", 2.0, 0.0),
                ("SOL", 50.0, 0.0),
                ("BNB", 5.0, 0.0),
                ("XRP", 1000.0, 0.0),
                ("DOGE", 5000.0, 0.0),
            ]
            conn.executemany(
                "INSERT INTO balances (asset, free, locked) VALUES (?, ?, ?)",
                defaults,
            )


def get_balances() -> Dict[str, float]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT asset, free FROM balances WHERE free > 0 OR locked > 0"
        ).fetchall()
        return {r["asset"]: r["free"] for r in rows}


def get_balance(asset: str) -> float:
    with get_db() as conn:
        row = conn.execute(
            "SELECT free FROM balances WHERE asset = ?", (asset,)
        ).fetchone()
        return float(row["free"]) if row else 0.0


def set_balance(asset: str, free: float, locked: float = 0.0):
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO balances (asset, free, locked) VALUES (?, ?, ?)
            ON CONFLICT(asset) DO UPDATE SET free = excluded.free, locked = excluded.locked
            """,
            (asset, free, locked),
        )


def adjust_balance(asset: str, delta_free: float, delta_locked: float = 0.0):
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO balances (asset, free, locked) VALUES (?, ?, ?)
            ON CONFLICT(asset) DO UPDATE SET
                free = free + excluded.free,
                locked = locked + excluded.locked
            """,
            (asset, delta_free, delta_locked),
        )


def insert_order(order: Dict[str, Any]):
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO orders
                (id, symbol, side, type, price, amount, filled, status, created_at, updated_at)
            VALUES
                (:id, :symbol, :side, :type, :price, :amount, :filled, :status, :created_at, :updated_at)
            """,
            order,
        )


def update_order(order_id: str, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [order_id]
    with get_db() as conn:
        conn.execute(f"UPDATE orders SET {cols} WHERE id = ?", vals)


def get_orders(status: Optional[str] = None, symbol: Optional[str] = None) -> List[Dict]:
    q = "SELECT * FROM orders WHERE 1=1"
    params: list = []
    if status:
        # support comma-separated statuses
        statuses = [s.strip() for s in status.split(",")]
        placeholders = ",".join("?" * len(statuses))
        q += f" AND status IN ({placeholders})"
        params.extend(statuses)
    if symbol:
        q += " AND symbol = ?"
        params.append(symbol)
    q += " ORDER BY created_at DESC"
    with get_db() as conn:
        rows = conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]


def get_order(order_id: str) -> Optional[Dict]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        return dict(row) if row else None


def insert_trade(trade: Dict[str, Any]):
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO trades (id, order_id, symbol, side, price, amount, created_at)
            VALUES (:id, :order_id, :symbol, :side, :price, :amount, :created_at)
            """,
            trade,
        )


def get_trades(symbol: Optional[str] = None, limit: int = 50) -> List[Dict]:
    q = "SELECT * FROM trades WHERE 1=1"
    params: list = []
    if symbol:
        q += " AND symbol = ?"
        params.append(symbol)
    q += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with get_db() as conn:
        rows = conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]


def reset_paper_account():
    """Wipe orders/trades and restore default balances."""
    with get_db() as conn:
        conn.execute("DELETE FROM orders")
        conn.execute("DELETE FROM trades")
        conn.execute("DELETE FROM balances")
    init_db()
