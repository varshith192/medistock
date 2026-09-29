"""Demo helpers. They only change operational state; every agent/memory step runs through
the same services the product uses (analyze, approve, outcome, retain, recall)."""
from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Any

from app.config import settings
from app.database import db
from app.hindsight import client as hs
from app.hindsight.retain import delete_document
from app.seed.seed_db import seed_database
from app.services import inventory, memory_service
from app.services.events import log_event

DEMO_MEDICINE = "MED-001"


def _set_stock(medicine_id: str, stock: int, demand: float) -> None:
    db.update("medicines", "id", medicine_id, {"current_stock": stock, "daily_demand": demand})
    today = date.today().isoformat()
    db.execute("""INSERT INTO stock_history (medicine_id, day, closing_stock, dispensed, received) VALUES (?,?,?,?,0)
                  ON CONFLICT(medicine_id, day) DO UPDATE SET closing_stock = excluded.closing_stock""",
               (medicine_id, today, stock, round(demand)))


def prepare_scenario() -> dict[str, Any]:
    """Put Amoxicillin back at its seeded situation (42 units, 15/day) without touching memory."""
    db.execute("UPDATE decisions SET status = 'superseded' WHERE medicine_id = ? AND status IN ('pending','approved')",
               (DEMO_MEDICINE,))
    db.execute("UPDATE orders SET status = 'cancelled' WHERE medicine_id = ? AND status = 'in_transit'", (DEMO_MEDICINE,))
    _set_stock(DEMO_MEDICINE, 42, 15)
    log_event("system", "Demo scenario prepared", "Amoxicillin 500mg set to 42 units at 15 units/day", DEMO_MEDICINE)
    return state()


def new_situation(medicine_id: str = DEMO_MEDICINE) -> dict[str, Any]:
    """Simulate the next demand cycle: stock is consumed back down to a low level."""
    med = inventory.get_medicine(medicine_id)
    if not med:
        raise ValueError("Medicine not found")
    demand = round(med["daily_demand"] + 1, 1)
    stock = round(demand * 2.6)
    _set_stock(medicine_id, stock, demand)
    log_event("detect", "New demand cycle — stock fell again",
              f"{med['name']} · {stock} units at {demand:g}/day ({stock / demand:.1f} days of cover)", medicine_id)
    return state()


def state() -> dict[str, Any]:
    med = inventory.get_medicine(DEMO_MEDICINE)
    decisions = db.query(
        "SELECT id, status, created_at, recommended_supplier_id, retained_document_id FROM decisions "
        "WHERE medicine_id = ? AND source = 'agent' ORDER BY created_at DESC LIMIT 5", (DEMO_MEDICINE,))
    agent_docs = db.query("SELECT * FROM memory_registry WHERE medicine_id = ? AND origin = 'agent' ORDER BY retained_at",
                          (DEMO_MEDICINE,))
    return {"medicine": med, "decisions": decisions, "agent_memories": agent_docs,
            "seed": memory_service.seed_state}


async def reset_all() -> dict[str, Any]:
    """Restore the original dataset and remove experiences the agent retained during demos."""
    removed = 0
    if settings.hindsight_configured:
        for row in db.query("SELECT document_id FROM memory_registry WHERE origin = 'agent'"):
            try:
                await delete_document(row["document_id"])
                removed += 1
            except Exception as exc:  # noqa: BLE001
                log_event("error", "Could not remove demo memory from Hindsight", hs._describe(exc))
    seed_database(force=True)
    memory_service.sync_incident_memory_status()
    log_event("system", "Demo data reset", f"Operational data restored; {removed} demo memories removed from Hindsight")
    # Re-run first-start behaviour (history sync + analysis of the most urgent medicines) in the background.
    from app.background import bootstrap
    db.set_setting("bootstrap_done", "0")
    asyncio.create_task(bootstrap())
    return {"removed_memories": removed, "reset_at": datetime.now().isoformat(timespec="seconds")}
