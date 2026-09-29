"""Dashboard, supplier intelligence and incident read models (computed from real records)."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.database import db
from app.services import inventory, risk


def _overdue_orders() -> list[dict[str, Any]]:
    rows = db.query(
        """SELECT o.*, m.name AS medicine_name, s.name AS supplier_name FROM orders o
           JOIN medicines m ON m.id = o.medicine_id JOIN suppliers s ON s.id = o.supplier_id
           WHERE o.status = 'in_transit' ORDER BY o.ordered_at""")
    now = datetime.now()
    out = []
    for r in rows:
        elapsed = (now - datetime.fromisoformat(r["ordered_at"])).total_seconds() / 86400
        r["elapsed_days"] = round(elapsed, 1)
        r["overdue"] = elapsed > r["expected_days"]
        out.append(r)
    return out


def suppliers_intelligence() -> list[dict[str, Any]]:
    perf = risk.supplier_performance()
    suppliers = db.query("SELECT * FROM suppliers ORDER BY id")
    meds = db.query("SELECT id, name, primary_supplier_id, approved_supplier_ids FROM medicines")
    out = []
    for s in suppliers:
        p = perf.get(s["id"], {"orders": 0, "avg_delivery_days": None, "expected_delivery_days": s["contracted_lead_days"],
                               "on_time_pct": 0, "delay_rate": 0})
        primary_for = [m["name"] for m in meds if m["primary_supplier_id"] == s["id"]]
        approved_for = [m["name"] for m in meds if s["id"] in m["approved_supplier_ids"]]
        by_medicine = db.query(
            """SELECT m.name AS medicine, COUNT(*) AS orders, ROUND(AVG(o.actual_days), 1) AS avg_days,
                      ROUND(AVG(o.expected_days), 1) AS expected_days, MAX(o.actual_days) AS worst_days,
                      SUM(CASE WHEN o.actual_days <= o.expected_days + 0.5 THEN 1 ELSE 0 END) AS on_time
               FROM orders o JOIN medicines m ON m.id = o.medicine_id
               WHERE o.supplier_id = ? AND o.actual_days IS NOT NULL GROUP BY o.medicine_id
               ORDER BY (AVG(o.actual_days) - AVG(o.expected_days)) DESC""", (s["id"],))
        recent = db.query(
            """SELECT o.id, o.ordered_at, o.quantity, o.expected_days, o.actual_days, o.status, o.urgency,
                      m.name AS medicine_name FROM orders o JOIN medicines m ON m.id = o.medicine_id
               WHERE o.supplier_id = ? ORDER BY o.ordered_at DESC LIMIT 12""", (s["id"],))
        delay_rate = p["delay_rate"]
        out.append({
            **s,
            "orders": p["orders"],
            "avg_delivery_days": p["avg_delivery_days"],
            "expected_delivery_days": p["expected_delivery_days"],
            "on_time_pct": p["on_time_pct"],
            "delay_rate_pct": delay_rate,
            "delay_rate_label": "High" if delay_rate >= 25 else "Medium" if delay_rate >= 12 else "Low",
            "reliability": risk.reliability_label(p["on_time_pct"]) if p["orders"] else "No history",
            "primary_for": primary_for,
            "approved_for_count": len(approved_for),
            "by_medicine": [{**r, "on_time_pct": round(100 * r["on_time"] / r["orders"])} for r in by_medicine],
            "recent_orders": recent,
        })
    return out


def list_incidents() -> list[dict[str, Any]]:
    return db.query(
        """SELECT i.*, m.name AS medicine_name, s.name AS supplier_name FROM incidents i
           JOIN medicines m ON m.id = i.medicine_id LEFT JOIN suppliers s ON s.id = i.supplier_id
           ORDER BY i.occurred_at DESC""")


def overview() -> dict[str, Any]:
    items = inventory.list_inventory()
    stock_risks = [i for i in items if i["risk_level"] in ("CRITICAL", "HIGH")]
    stock_risks.sort(key=lambda i: i["days_remaining"])
    expiry = sorted([i for i in items if i["expiry_risk"]], key=lambda i: i["days_to_expiry"])
    suppliers = suppliers_intelligence()
    supplier_issues = [s for s in suppliers if s["reliability"] == "Needs Attention"]
    overdue = [o for o in _overdue_orders() if o["overdue"]]
    incidents = [i for i in list_incidents() if i["status"] != "resolved"]
    completed = db.query("SELECT outcome FROM decisions WHERE status = 'completed' AND outcome IS NOT NULL")
    successes = sum(1 for d in completed if d["outcome"]["result"] == "successful")
    pending = db.query_one("SELECT COUNT(*) AS n FROM decisions WHERE status = 'pending'")["n"]
    awaiting = db.query_one("SELECT COUNT(*) AS n FROM decisions WHERE status = 'approved'")["n"]
    retained = db.query_one("SELECT COUNT(*) AS n FROM memory_registry")["n"]
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    memory_influenced = db.query_one(
        "SELECT COUNT(*) AS n FROM decisions WHERE source = 'agent' AND memory_used != '[]' AND created_at >= ?",
        (week_ago,))["n"]
    return {
        "metrics": {
            "total_medicines": len(items),
            "stock_risks": len(stock_risks),
            "critical": sum(1 for i in stock_risks if i["risk_level"] == "CRITICAL"),
            "high": sum(1 for i in stock_risks if i["risk_level"] == "HIGH"),
            "expiry_risks": len(expiry),
            "expiry_threshold_days": risk.expiry_threshold_days(),
            "pending_decisions": pending,
            "awaiting_outcome": awaiting,
            "supplier_issues": len(supplier_issues),
            "decisions_completed": len(completed),
            "success_rate": round(100 * successes / len(completed)) if completed else None,
            "experiences_retained": retained,
            "memory_influenced_decisions_7d": memory_influenced,
        },
        "stock_risks": stock_risks[:6],
        "expiry_risks": expiry[:6],
        "supplier_issues": [{"id": s["id"], "name": s["name"], "legal_name": s["legal_name"],
                             "avg_delivery_days": s["avg_delivery_days"], "expected_delivery_days": s["expected_delivery_days"],
                             "on_time_pct": s["on_time_pct"]} for s in supplier_issues],
        "overdue_orders": overdue,
        "open_incidents": incidents[:6],
        "risk_distribution": {lvl: sum(1 for i in items if i["risk_level"] == lvl) for lvl in risk.RISK_ORDER},
    }
