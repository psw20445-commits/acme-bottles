from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "acme_bottles.sqlite3"


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    with connect() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS purchase_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                po_number TEXT NOT NULL UNIQUE,
                customer_name TEXT NOT NULL,
                product_type TEXT NOT NULL CHECK (product_type IN ('1-Liter Bottle', '1-Gallon Bottle')),
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                notes TEXT,
                order_date TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS supply_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                material_type TEXT NOT NULL CHECK (material_type IN ('PET Resin', 'PTA', 'Ethylene Glycol')),
                quantity_kg REAL NOT NULL CHECK (quantity_kg > 0),
                supplier_name TEXT,
                tracking_number TEXT NOT NULL,
                eta TEXT NOT NULL,
                order_date TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_purchase_orders_order_date
            ON purchase_orders(order_date, id)
            """
        )
        db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_supply_orders_order_date
            ON supply_orders(order_date, id)
            """
        )
        db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_supply_orders_eta
            ON supply_orders(eta, id)
            """
        )
        db.commit()


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]


def next_po_number(db: sqlite3.Connection, year: int | None = None) -> str:
    if year is None:
        year = datetime.now(timezone.utc).year
    row = db.execute(
        """
        SELECT COALESCE(MAX(CAST(SUBSTR(po_number, -4) AS INTEGER)), 0) AS last_number
        FROM purchase_orders
        WHERE po_number LIKE ?
        """,
        (f"PO-{year}-%",),
    ).fetchone()
    return f"PO-{year}-{int(row['last_number']) + 1:04d}"
