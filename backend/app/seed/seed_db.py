"""Builds the local SQLite operational dataset."""
from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta

from app.database import db
from app.seed.data import (DEMAND_SPIKES, MEDICINES, SUPPLIER_A_ANTIBIOTIC_PROFILE, SUPPLIER_PROFILE,
                           SUPPLIERS)
from app.seed.memory_seed import seed_experiences

HISTORY_DAYS = 30
ANTIBIOTICS_A = {"MED-001", "MED-007", "MED-015", "MED-016"}


def _iso(d: date, hour: int = 10, minute: int = 0) -> str:
    return datetime.combine(d, time(hour, minute)).isoformat(timespec="seconds")


def _round_up(value: float, step: int) -> int:
    step = max(step, 1)
    return max(step, int(-(-value // step)) * step)


def _amoxicillin_history(today: date) -> list[tuple[date, int, int, int]]:
    """Scripted history for the demo medicine (closing, dispensed, received)."""
    rows: list[tuple[date, int, int, int]] = []
    # Days -29..-17: routine decline from a routine delivery
    stock = 252
    for offset in range(29, 16, -1):
        dispensed = 14 + (offset % 3) - 1
        stock -= dispensed
        rows.append((today - timedelta(days=offset), stock, dispensed, 0))
    scripted = {
        16: (14, 0),   # emergency order placed with Supplier A; closes at 55
        15: (16, 0),
        14: (16, 0),
        13: (15, 0),   # stock falls to 8, dispensing rationed
        12: (12, 100), # Supplier A delivers after 4 days
        11: (20, 0),   # demand spike begins
        10: (22, 0),   # urgent order placed with Supplier B; closes at 54
        9: (22, 150),  # Supplier B delivers in 1.5 days
        8: (17, 0), 7: (16, 0), 6: (15, 0), 5: (16, 0), 4: (15, 0), 3: (16, 0), 2: (15, 0), 1: (16, 0),
    }
    for offset in range(16, 0, -1):
        dispensed, received = scripted[offset]
        stock = stock - dispensed + received
        rows.append((today - timedelta(days=offset), stock, dispensed, received))
    return rows  # yesterday closes at 56; 14 units dispensed so far today -> 42 on hand


def _generic_history(rng: random.Random, med: tuple, today: date) -> list[tuple[date, int, int, int]]:
    """Walk backwards from today's stock, inserting deliveries to form a realistic sawtooth."""
    med_id, stock_now, demand, pack = med[0], med[5], med[6], med[7]
    spike = DEMAND_SPIKES.get(med_id)
    cap = demand * 24
    rows: list[tuple[date, int, int, int]] = []
    stock = stock_now
    for offset in range(1, HISTORY_DAYS + 1):
        day = today - timedelta(days=offset)
        level = demand
        if spike and offset > spike[0]:
            level = demand * spike[1]
        dispensed = max(0, round(rng.gauss(level, level * 0.18)))
        received = 0
        prev = stock + dispensed
        if prev > cap and offset > 2:
            received = _round_up(demand * rng.uniform(12, 18), pack)
            prev = max(round(demand * rng.uniform(1.5, 4)), prev - received)
            received = stock + dispensed - prev
            if received <= 0:
                received, prev = 0, stock + dispensed
        rows.append((day, stock, dispensed, received))
        stock = prev
    rows.reverse()
    return rows


def _sample_delivery(rng: random.Random, supplier_id: str, medicine_id: str, lead: float) -> float:
    mean, spread = SUPPLIER_PROFILE[supplier_id]
    if supplier_id == "SUP-A" and medicine_id in ANTIBIOTICS_A:
        mean, spread = SUPPLIER_A_ANTIBIOTIC_PROFILE
    return round(max(0.5, lead * rng.gauss(mean, spread)) * 2) / 2


def seed_database(force: bool = False) -> bool:
    """Create schema and seed data. Returns True if seeding happened."""
    if force:
        db.drop_operational()
    db.init_schema()
    if db.query_one("SELECT COUNT(*) AS n FROM medicines")["n"] > 0:
        return False

    rng = random.Random(360)
    today = date.today()
    suppliers = {s[0]: s for s in SUPPLIERS}

    for s in SUPPLIERS:
        db.insert("suppliers", dict(zip(
            ["id", "name", "legal_name", "city", "contracted_lead_days", "min_order_qty", "contact_email", "phone"], s)))

    order_seq = 4100
    for m in MEDICINES:
        (mid, name, generic, form, category, stock, demand, pack, cost, exp_days, storage,
         primary, approved, essential) = m
        db.insert("medicines", {
            "id": mid, "name": name, "generic_name": generic, "form": form, "category": category,
            "current_stock": stock, "daily_demand": demand, "pack_size": pack, "unit_cost": cost,
            "expiry_date": (today + timedelta(days=exp_days)).isoformat(),
            "batch_no": f"B{rng.randint(24000, 26999)}{chr(65 + rng.randint(0, 5))}",
            "storage": storage, "primary_supplier_id": primary, "approved_supplier_ids": approved,
            "essential": essential,
        })

        history = _amoxicillin_history(today) if mid == "MED-001" else _generic_history(rng, m, today)
        with db.get_conn() as conn:
            conn.executemany(
                "INSERT INTO stock_history (medicine_id, day, closing_stock, dispensed, received) VALUES (?,?,?,?,?)",
                [(mid, d.isoformat(), c, disp, rec) for d, c, disp, rec in history])

        if mid == "MED-001":
            continue  # Amoxicillin orders are scripted below.

        # Orders behind every delivery in the 30-day history, plus older orders for supplier analytics.
        receipts = [(d, rec) for d, _, _, rec in history if rec > 0]
        for extra in range(rng.randint(2, 3)):
            receipts.append((today - timedelta(days=rng.randint(35, 88)), _round_up(demand * rng.uniform(12, 18), pack)))
        for recv_day, qty in receipts:
            supplier_id = primary if rng.random() < 0.8 else rng.choice(approved)
            lead = suppliers[supplier_id][4]
            actual = _sample_delivery(rng, supplier_id, mid, lead)
            ordered = recv_day - timedelta(days=round(actual))
            order_seq += 1
            db.insert("orders", {
                "id": f"PO-{order_seq}", "medicine_id": mid, "supplier_id": supplier_id, "quantity": qty,
                "ordered_at": _iso(ordered, 9 + rng.randint(0, 7), rng.choice([0, 15, 30, 45])),
                "expected_days": lead, "actual_days": actual, "delivered_qty": qty,
                "status": "delivered_late" if actual > lead + 0.5 else "delivered",
                "urgency": "routine", "decision_id": None,
            })

    # Scripted Amoxicillin order history (the demo storyline).
    amox_orders = [
        ("PO-3877", "SUP-A", 300, today - timedelta(days=78), 2.0, 2.5, "routine", None),
        ("PO-3990", "SUP-A", 300, today - timedelta(days=47), 2.0, 3.0, "routine", None),
        ("PO-4051", "SUP-A", 250, today - timedelta(days=32), 2.0, 2.5, "routine", None),
        ("PO-4088", "SUP-A", 100, today - timedelta(days=16), 2.0, 4.0, "emergency", "DEC-2001"),
        ("PO-4096", "SUP-B", 150, today - timedelta(days=10), 2.0, 1.5, "urgent", "DEC-2002"),
    ]
    amox_orders = [("MED-001", *o) for o in amox_orders] + [
        # Cold-chain backup supplier history (Supplier E).
        ("MED-005", "PO-4062", "SUP-E", 20, today - timedelta(days=27), 1.0, 1.0, "emergency", None),
        ("MED-010", "PO-4012", "SUP-E", 20, today - timedelta(days=58), 1.0, 1.0, "urgent", None),
        ("MED-047", "PO-3951", "SUP-E", 15, today - timedelta(days=71), 1.0, 1.5, "routine", None),
        ("MED-005", "PO-3902", "SUP-E", 25, today - timedelta(days=84), 1.0, 1.0, "urgent", None),
        ("MED-005", "PO-4001", "SUP-D", 40, today - timedelta(days=31), 2.0, 5.0, "urgent", "DEC-1975"),
    ]
    for mid, oid, sup, qty, ordered, lead, actual, urgency, dec in amox_orders:
        db.insert("orders", {
            "id": oid, "medicine_id": mid, "supplier_id": sup, "quantity": qty,
            "ordered_at": _iso(ordered, 11, 20), "expected_days": lead, "actual_days": actual,
            "delivered_qty": qty, "status": "delivered_late" if actual > lead + 0.5 else "delivered",
            "urgency": urgency, "decision_id": dec,
        })
    # Open (in-transit) routine orders.
    for oid, mid, sup, qty, days_ago in [("PO-4130", "MED-008", "SUP-F", 400, 2), ("PO-4131", "MED-012", "SUP-C", 300, 1)]:
        lead = suppliers[sup][4]
        db.insert("orders", {
            "id": oid, "medicine_id": mid, "supplier_id": sup, "quantity": qty,
            "ordered_at": _iso(today - timedelta(days=days_ago), 15, 10), "expected_days": lead,
            "actual_days": None, "delivered_qty": None, "status": "in_transit", "urgency": "routine",
            "decision_id": None,
        })

    _seed_decisions(today)
    _seed_incidents(today)
    db.set_setting("expiry_threshold_days", "60")
    db.set_setting("target_cover_days", "7")
    db.set_setting("seeded_on", today.isoformat())
    db.insert("events", {"ts": datetime.now().isoformat(timespec="seconds"), "kind": "system",
                         "title": "Operational dataset loaded",
                         "detail": f"{len(MEDICINES)} medicines, {len(SUPPLIERS)} suppliers, 30-day stock history",
                         "medicine_id": None, "decision_id": None, "meta": None})
    return True


def _seed_decisions(today: date) -> None:
    """Decisions taken by the manager before the agent was introduced (manual history)."""
    base = {
        "source": "manual", "status": "completed", "engine": "manual", "why": [], "memory_used": [],
        "memories_recalled": [], "alternatives": [], "baseline": None, "trace": [], "rejected_at": None,
        "manager_note": None, "retained_document_id": None,
    }
    rows = [
        {**base, "id": "DEC-2001", "medicine_id": "MED-001", "created_at": _iso(today - timedelta(days=16), 11, 5),
         "risk_level": "HIGH", "days_remaining": 3.7, "current_stock": 55, "daily_demand": 15,
         "recommended_supplier_id": "SUP-A", "recommended_quantity": 100, "planning_lead_days": 2.0,
         "final_supplier_id": "SUP-A", "final_quantity": 100, "urgency": "emergency", "confidence": "medium",
         "headline": "Emergency reorder from primary supplier", "assessment": "Stock below reorder point.",
         "reason": "Primary supplier with 2-day contracted lead time.", "order_id": "PO-4088",
         "approved_at": _iso(today - timedelta(days=16), 11, 12),
         "outcome": {"result": "delayed", "delivered_quantity": 100, "delivery_days": 4.0, "stockout": "near",
                     "summary": "Delivered after 4 days; stock fell to 8 units and dispensing was rationed."},
         "outcome_at": _iso(today - timedelta(days=12), 15, 40), "retained_document_id": "seed-amox-supplier-a-delay"},
        {**base, "id": "DEC-2002", "medicine_id": "MED-001", "created_at": _iso(today - timedelta(days=10), 11, 0),
         "risk_level": "HIGH", "days_remaining": 2.5, "current_stock": 54, "daily_demand": 22,
         "recommended_supplier_id": "SUP-B", "recommended_quantity": 150, "planning_lead_days": 2.0,
         "final_supplier_id": "SUP-B", "final_quantity": 150, "urgency": "urgent", "confidence": "medium",
         "headline": "Urgent reorder from Supplier B", "assessment": "Demand spike with 2.5 days of cover.",
         "reason": "Manager switched to Supplier B after Supplier A's 4-day delay the previous week.",
         "order_id": "PO-4096", "approved_at": _iso(today - timedelta(days=10), 11, 14),
         "outcome": {"result": "successful", "delivered_quantity": 150, "delivery_days": 1.5, "stockout": "avoided",
                     "summary": "Delivered in 1.5 days; stock never fell below 32 units."},
         "outcome_at": _iso(today - timedelta(days=9), 0, 30), "retained_document_id": "seed-amox-supplier-b-success"},
        {**base, "id": "DEC-1987", "medicine_id": "MED-003", "created_at": _iso(today - timedelta(days=23), 10, 40),
         "risk_level": "CRITICAL", "days_remaining": 2.0, "current_stock": 16, "daily_demand": 8,
         "recommended_supplier_id": "SUP-B", "recommended_quantity": 60, "planning_lead_days": 2.0,
         "final_supplier_id": "SUP-B", "final_quantity": 60, "urgency": "urgent", "confidence": "medium",
         "headline": "Urgent reorder from primary supplier", "assessment": "Two days of cover remaining.",
         "reason": "Primary supplier, 2-day contracted lead time.", "order_id": None,
         "approved_at": _iso(today - timedelta(days=23), 10, 55),
         "outcome": {"result": "successful", "delivered_quantity": 60, "delivery_days": 2.0, "stockout": "avoided",
                     "summary": "Delivered on time."},
         "outcome_at": _iso(today - timedelta(days=21), 12, 0), "retained_document_id": "seed-azithro-supplier-b"},
        {**base, "id": "DEC-1975", "medicine_id": "MED-005", "created_at": _iso(today - timedelta(days=31), 9, 30),
         "risk_level": "HIGH", "days_remaining": 3.2, "current_stock": 19, "daily_demand": 6,
         "recommended_supplier_id": "SUP-D", "recommended_quantity": 40, "planning_lead_days": 2.0,
         "final_supplier_id": "SUP-D", "final_quantity": 40, "urgency": "urgent", "confidence": "medium",
         "headline": "Reorder from cold-chain primary supplier", "assessment": "Cover below 4 days.",
         "reason": "Primary cold-chain supplier.", "order_id": None,
         "approved_at": _iso(today - timedelta(days=31), 9, 45),
         "outcome": {"result": "failed", "delivered_quantity": 20, "delivery_days": 5.0, "stockout": "avoided_by_backup",
                     "summary": "Delivered 3 days late; 20 pens failed temperature check. Supplier E backup order used."},
         "outcome_at": _iso(today - timedelta(days=26), 16, 0), "retained_document_id": "seed-insulin-coldchain-delay"},
    ]
    for row in rows:
        db.insert("decisions", row)


def _seed_incidents(today: date) -> None:
    seed_docs = {e["incident_id"]: e["document_id"] for e in seed_experiences() if e["incident_id"]}
    rows = [
        ("INC-1001", "MED-001", "supplier_delay", "Amoxicillin stock-out risk", "high", 16,
         "Supplier A delivered the emergency order in 4 days against a 2-day contracted lead time",
         "Emergency reorder of 100 units from Supplier A; dispensing rationed", "SUP-A",
         "Near stock-out — stock fell to 8 units", "resolved", "DEC-2001"),
        ("INC-1002", "MED-001", "emergency_replenishment", "Amoxicillin demand spike", "high", 10,
         "Seasonal respiratory demand spike (~22 units/day) with 2.5 days of cover",
         "Urgent order of 150 units from Supplier B", "SUP-B", "Delivered in 1.5 days — stock-out avoided",
         "resolved", "DEC-2002"),
        ("INC-1003", "MED-036", "expiry", "Cefixime expiry write-off", "medium", 39,
         "Bulk order of 400 units against ~6 units/day demand", "180 tablets written off; order cap introduced",
         "SUP-C", "Write-off of 180 tablets", "resolved", None),
        ("INC-1004", "MED-005", "supplier_delay", "Insulin Glargine cold-chain failure", "critical", 26,
         "Supplier D delivered 3 days late; one carton failed 2-8°C check",
         "Backup order from Supplier E (1-day delivery)", "SUP-D", "Stock-out avoided via backup supplier",
         "resolved", "DEC-1975"),
        ("INC-1005", "MED-006", "demand_spike", "ORS monsoon demand spike", "medium", 33,
         "Seasonal diarrhoeal cases tripled ORS demand", "Standing order with Supplier C",
         "SUP-C", "Stock maintained; cover dipped below 2 days twice", "resolved", None),
        ("INC-1006", "MED-003", "emergency_replenishment", "Azithromycin low cover", "high", 23,
         "Cover dropped to 2 days", "Urgent order of 60 units from Supplier B", "SUP-B",
         "Delivered on time — no stock-out", "resolved", "DEC-1987"),
        ("INC-1007", "MED-004", "stock_out", "Salbutamol inhaler stock-out", "critical", 5,
         "Routine order from Supplier C arrived 2 days late during a seasonal demand rise",
         "Inhalers borrowed from sister store; routine order received", "SUP-C",
         "Stock-out for 1 day", "monitoring", None),
        ("INC-1008", "MED-008", "supplier_delay", "Pantoprazole delivery delay", "medium", 7,
         "Supplier F dispatch delayed by transporter strike", "Order still in transit; demand monitored",
         "SUP-F", "Pending delivery", "open", None),
        ("INC-1009", "MED-002", "demand_spike", "Paracetamol fever-season spike", "low", 21,
         "Viral fever cases raised demand by ~40% for 10 days", "Increased routine order quantity",
         "SUP-B", "Stock maintained", "resolved", None),
        ("INC-1010", "MED-043", "expiry", "Dexamethasone short-dated batch", "medium", 3,
         "Batch expires in 28 days with ~37 days of stock on hand", "Flagged for redistribution",
         None, "Pending", "open", None),
        ("INC-1011", "MED-047", "expiry", "Insulin Regular short-dated batch", "high", 2,
         "Cold-chain batch expires in 20 days with ~28 days of stock on hand", "Return request raised with Supplier D",
         "SUP-D", "Pending supplier response", "open", None),
        ("INC-1012", "MED-010", "stock_out_risk", "Enoxaparin low cover", "high", 1,
         "Cover fell below 4 days", "Awaiting agent analysis", "SUP-D", "Pending", "open", None),
    ]
    for (iid, mid, typ, title, sev, days_ago, cause, action, sup, outcome, status, dec) in rows:
        doc = seed_docs.get(iid)
        db.insert("incidents", {
            "id": iid, "medicine_id": mid, "type": typ, "title": title, "severity": sev,
            "occurred_at": _iso(today - timedelta(days=days_ago), 11, 0), "cause": cause, "action": action,
            "supplier_id": sup, "outcome": outcome, "status": status, "decision_id": dec,
            # Memory status becomes 'retained' only after the Hindsight retain call succeeds.
            "memory_document_id": doc, "memory_status": "pending" if doc else "not_retained",
        })
