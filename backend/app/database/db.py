"""SQLite storage for current operational data (inventory, suppliers, orders, decisions).

Persistent *experience* (what happened, why, what we learned) lives in Hindsight,
not here. This database is the system of record for the current state.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator

from app.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS suppliers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    legal_name TEXT NOT NULL,
    city TEXT NOT NULL,
    contracted_lead_days REAL NOT NULL,
    min_order_qty INTEGER NOT NULL,
    contact_email TEXT NOT NULL,
    phone TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS medicines (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    generic_name TEXT NOT NULL,
    form TEXT NOT NULL,
    category TEXT NOT NULL,
    current_stock INTEGER NOT NULL,
    daily_demand REAL NOT NULL,
    pack_size INTEGER NOT NULL,
    unit_cost REAL NOT NULL,
    expiry_date TEXT NOT NULL,
    batch_no TEXT NOT NULL,
    storage TEXT NOT NULL,
    primary_supplier_id TEXT NOT NULL REFERENCES suppliers(id),
    approved_supplier_ids TEXT NOT NULL,
    essential INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS stock_history (
    medicine_id TEXT NOT NULL REFERENCES medicines(id),
    day TEXT NOT NULL,
    closing_stock INTEGER NOT NULL,
    dispensed INTEGER NOT NULL,
    received INTEGER NOT NULL,
    PRIMARY KEY (medicine_id, day)
);

CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    medicine_id TEXT NOT NULL REFERENCES medicines(id),
    supplier_id TEXT NOT NULL REFERENCES suppliers(id),
    quantity INTEGER NOT NULL,
    ordered_at TEXT NOT NULL,
    expected_days REAL NOT NULL,
    actual_days REAL,
    delivered_qty INTEGER,
    status TEXT NOT NULL,
    urgency TEXT NOT NULL,
    decision_id TEXT
);

CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    medicine_id TEXT NOT NULL REFERENCES medicines(id),
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    severity TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    cause TEXT NOT NULL,
    action TEXT NOT NULL,
    supplier_id TEXT,
    outcome TEXT NOT NULL,
    status TEXT NOT NULL,
    decision_id TEXT,
    memory_document_id TEXT,
    memory_status TEXT NOT NULL DEFAULT 'not_retained'
);

CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY,
    medicine_id TEXT NOT NULL REFERENCES medicines(id),
    created_at TEXT NOT NULL,
    status TEXT NOT NULL,
    source TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    days_remaining REAL NOT NULL,
    current_stock INTEGER NOT NULL,
    daily_demand REAL NOT NULL,
    recommended_supplier_id TEXT NOT NULL,
    recommended_quantity INTEGER NOT NULL,
    planning_lead_days REAL NOT NULL,
    final_supplier_id TEXT,
    final_quantity INTEGER,
    urgency TEXT NOT NULL,
    confidence TEXT NOT NULL,
    headline TEXT NOT NULL,
    assessment TEXT NOT NULL,
    reason TEXT NOT NULL,
    why TEXT NOT NULL,
    memory_used TEXT NOT NULL,
    memories_recalled TEXT NOT NULL,
    alternatives TEXT NOT NULL,
    baseline TEXT,
    memory_state TEXT,
    recall_query TEXT,
    engine TEXT NOT NULL,
    trace TEXT NOT NULL,
    order_id TEXT,
    manager_note TEXT,
    approved_at TEXT,
    rejected_at TEXT,
    outcome TEXT,
    outcome_at TEXT,
    retained_document_id TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    detail TEXT,
    medicine_id TEXT,
    decision_id TEXT,
    meta TEXT
);

CREATE TABLE IF NOT EXISTS memory_registry (
    document_id TEXT PRIMARY KEY,
    origin TEXT NOT NULL,
    category TEXT NOT NULL,
    medicine_id TEXT,
    retained_at TEXT NOT NULL,
    items_count INTEGER
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

JSON_COLUMNS = {
    "approved_supplier_ids", "why", "memory_used", "memories_recalled", "alternatives",
    "baseline", "trace", "outcome", "meta",
}


def _connect() -> sqlite3.Connection:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.database_path, timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_schema() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def drop_operational() -> None:
    """Drop operational tables. The memory registry (what exists in Hindsight) is kept."""
    with get_conn() as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        for table in ("events", "decisions", "incidents", "orders", "stock_history", "medicines", "suppliers"):
            conn.execute(f"DROP TABLE IF EXISTS {table}")


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    out = dict(row)
    for key in JSON_COLUMNS & out.keys():
        value = out[key]
        # Only structured values are stored as JSON; plain text columns that share a name stay text.
        if isinstance(value, str) and value[:1] in ("[", "{", '"'):
            out[key] = json.loads(value)
    return out


def _encode(key: str, value: Any) -> Any:
    return json.dumps(value) if key in JSON_COLUMNS and isinstance(value, (dict, list)) else value


def query(sql: str, params: tuple | dict = ()) -> list[dict[str, Any]]:
    with get_conn() as conn:
        return [row_to_dict(r) for r in conn.execute(sql, params).fetchall()]


def query_one(sql: str, params: tuple | dict = ()) -> dict[str, Any] | None:
    with get_conn() as conn:
        return row_to_dict(conn.execute(sql, params).fetchone())


def execute(sql: str, params: tuple | dict = ()) -> None:
    with get_conn() as conn:
        conn.execute(sql, params)


def insert(table: str, data: dict[str, Any]) -> None:
    values = {k: _encode(k, v) for k, v in data.items()}
    cols = ", ".join(values)
    marks = ", ".join(f":{k}" for k in values)
    with get_conn() as conn:
        conn.execute(f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({marks})", values)


def update(table: str, key: str, key_value: Any, data: dict[str, Any]) -> None:
    values = {k: _encode(k, v) for k, v in data.items()}
    assignments = ", ".join(f"{k} = :{k}" for k in values)
    values["__key"] = key_value
    with get_conn() as conn:
        conn.execute(f"UPDATE {table} SET {assignments} WHERE {key} = :__key", values)


def get_setting(key: str, default: str | None = None) -> str | None:
    row = query_one("SELECT value FROM app_settings WHERE key = ?", (key,))
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", (key, value))
