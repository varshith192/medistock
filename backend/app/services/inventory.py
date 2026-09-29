"""Read models over the operational database."""
from __future__ import annotations

from typing import Any

from app.database import db
from app.services import risk

def active_decisions() -> dict[str, dict[str, Any]]:
    rows = db.query(
        "SELECT id, medicine_id, status, created_at FROM decisions WHERE status IN ('pending','approved') "
        "ORDER BY created_at DESC")
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        out.setdefault(r["medicine_id"], r)
    return out


def list_inventory() -> list[dict[str, Any]]:
    perf = risk.supplier_performance()
    active = active_decisions()
    suppliers = {s["id"]: s["name"] for s in db.query("SELECT id, name FROM suppliers")}
    meds = db.query("SELECT * FROM medicines ORDER BY name")
    out = []
    for m in meds:
        item = risk.assess_medicine(m, perf, active.get(m["id"]))
        item["primary_supplier_name"] = suppliers.get(m["primary_supplier_id"])
        out.append(item)
    return out


def get_medicine(medicine_id: str) -> dict[str, Any] | None:
    med = db.query_one("SELECT * FROM medicines WHERE id = ?", (medicine_id,))
    if not med:
        return None
    item = risk.assess_medicine(med, None, active_decisions().get(medicine_id))
    sup = db.query_one("SELECT name FROM suppliers WHERE id = ?", (med["primary_supplier_id"],))
    item["primary_supplier_name"] = sup["name"] if sup else None
    return item


def supplier_terms(medicine: dict[str, Any]) -> list[dict[str, Any]]:
    """Contracted terms + open orders for each approved supplier of a medicine."""
    out = []
    for sid in medicine["approved_supplier_ids"]:
        s = db.query_one("SELECT * FROM suppliers WHERE id = ?", (sid,))
        if not s:
            continue
        open_orders = db.query(
            "SELECT id, quantity, ordered_at, expected_days FROM orders WHERE supplier_id = ? AND medicine_id = ? "
            "AND status = 'in_transit'", (sid, medicine["id"]))
        out.append({
            "id": s["id"], "name": s["name"], "legal_name": s["legal_name"],
            "contracted_lead_days": s["contracted_lead_days"], "min_order_qty": s["min_order_qty"],
            "is_primary": sid == medicine["primary_supplier_id"], "open_orders": open_orders,
        })
    return out


def medicine_detail(medicine_id: str) -> dict[str, Any] | None:
    med = get_medicine(medicine_id)
    if not med:
        return None
    history = db.query(
        "SELECT day, closing_stock, dispensed, received FROM stock_history WHERE medicine_id = ? ORDER BY day",
        (medicine_id,))
    orders = db.query(
        """SELECT o.*, s.name AS supplier_name FROM orders o JOIN suppliers s ON s.id = o.supplier_id
           WHERE o.medicine_id = ? ORDER BY o.ordered_at DESC""", (medicine_id,))
    # Per-supplier delivery performance for this medicine.
    perf_rows = db.query(
        """SELECT o.supplier_id, s.name, COUNT(*) AS orders, AVG(o.actual_days) AS avg_days,
                  AVG(o.expected_days) AS exp_days, MAX(o.actual_days) AS worst_days,
                  SUM(CASE WHEN o.actual_days <= o.expected_days + 0.5 THEN 1 ELSE 0 END) AS on_time
           FROM orders o JOIN suppliers s ON s.id = o.supplier_id
           WHERE o.medicine_id = ? AND o.actual_days IS NOT NULL GROUP BY o.supplier_id""", (medicine_id,))
    supplier_perf = [{
        "supplier_id": r["supplier_id"], "supplier_name": r["name"], "orders": r["orders"],
        "avg_delivery_days": round(r["avg_days"], 1), "expected_delivery_days": round(r["exp_days"], 1),
        "worst_delivery_days": r["worst_days"], "on_time_pct": round(100 * r["on_time"] / r["orders"]),
    } for r in perf_rows]
    incidents = db.query(
        "SELECT * FROM incidents WHERE medicine_id = ? ORDER BY occurred_at DESC", (medicine_id,))
    # Same shape as the Decision Center (timeline, supplier names), so the drawer can render decision cards.
    from app.agents.inventory_agent import list_decisions  # local import: the agent module imports this one

    decisions = [d for d in list_decisions(medicine_id=medicine_id) if d["status"] != "superseded"]
    return {
        "medicine": med,
        "demand_trend": risk.demand_trend(medicine_id),
        "history": history,
        "orders": orders,
        "supplier_performance": supplier_perf,
        "approved_suppliers": supplier_terms(med),
        "incidents": incidents,
        "decisions": decisions,
    }
