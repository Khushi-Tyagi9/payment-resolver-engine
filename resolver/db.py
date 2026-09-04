"""SQLite storage: orders_batch (input) and audit_log (output)."""

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "payment_resolver.db"


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def reset_schema(conn: sqlite3.Connection) -> None:
    """Drop and recreate both tables so each full batch run starts clean."""
    conn.executescript(
        """
        DROP TABLE IF EXISTS audit_log;
        DROP TABLE IF EXISTS orders_batch;

        CREATE TABLE orders_batch (
            record_id TEXT PRIMARY KEY,
            razorpay_payment_id TEXT NOT NULL,
            order_id TEXT NOT NULL,
            amount INTEGER NOT NULL,
            razorpay_status TEXT NOT NULL,
            merchant_order_status TEXT NOT NULL,
            event_type TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );

        CREATE TABLE audit_log (
            record_id TEXT PRIMARY KEY REFERENCES orders_batch(record_id),
            correlation_ok INTEGER NOT NULL,
            razorpay_status TEXT NOT NULL,
            merchant_status TEXT NOT NULL,
            drift_direction TEXT,
            action_taken TEXT NOT NULL,
            reason TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );
        """
    )
    conn.commit()


def seed_orders_batch(conn: sqlite3.Connection, records: list[dict]) -> None:
    conn.executemany(
        """
        INSERT INTO orders_batch
            (record_id, razorpay_payment_id, order_id, amount, razorpay_status,
             merchant_order_status, event_type, timestamp)
        VALUES (:record_id, :razorpay_payment_id, :order_id, :amount, :razorpay_status,
                :merchant_order_status, :event_type, :timestamp)
        """,
        records,
    )
    conn.commit()


def fetch_orders_batch(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM orders_batch ORDER BY timestamp, record_id").fetchall()
    return [dict(row) for row in rows]


def insert_audit_row(conn: sqlite3.Connection, row: dict) -> bool:
    """Insert one audit_log row. Returns False (no-op) if record_id was
    already claimed — the idempotency guarantee: each record processed
    exactly once."""
    cur = conn.execute(
        """
        INSERT OR IGNORE INTO audit_log
            (record_id, correlation_ok, razorpay_status, merchant_status,
             drift_direction, action_taken, reason, timestamp)
        VALUES (:record_id, :correlation_ok, :razorpay_status, :merchant_status,
                :drift_direction, :action_taken, :reason, :timestamp)
        """,
        row,
    )
    conn.commit()
    return cur.rowcount == 1


def update_merchant_status(conn: sqlite3.Connection, order_id: str, new_status: str) -> None:
    conn.execute(
        "UPDATE orders_batch SET merchant_order_status = ? WHERE order_id = ?",
        (new_status, order_id),
    )
    conn.commit()


def fetch_audit_log(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM audit_log ORDER BY timestamp, record_id").fetchall()
    return [dict(row) for row in rows]
