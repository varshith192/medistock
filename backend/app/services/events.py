"""Agent / memory activity log shown in the UI. Only real operations are logged."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.database import db


def log_event(kind: str, title: str, detail: str | None = None, medicine_id: str | None = None,
              decision_id: str | None = None, meta: dict[str, Any] | None = None) -> None:
    db.insert("events", {
        "ts": datetime.now().isoformat(timespec="seconds"), "kind": kind, "title": title, "detail": detail,
        "medicine_id": medicine_id, "decision_id": decision_id, "meta": meta,
    })


def recent_events(limit: int = 30, kinds: list[str] | None = None) -> list[dict[str, Any]]:
    sql = """SELECT e.*, m.name AS medicine_name FROM events e
             LEFT JOIN medicines m ON m.id = e.medicine_id"""
    params: list[Any] = []
    if kinds:
        sql += f" WHERE e.kind IN ({','.join('?' for _ in kinds)})"
        params.extend(kinds)
    sql += " ORDER BY e.id DESC LIMIT ?"
    params.append(limit)
    return db.query(sql, tuple(params))
