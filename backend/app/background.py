"""Background agent loop: periodic risk scan, Hindsight seeding and first-run analysis."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from app.agents import inventory_agent, llm
from app.config import settings
from app.database import db
from app.services import inventory, memory_service
from app.services.events import log_event

log = logging.getLogger("medistock")
SCAN_INTERVAL_SECONDS = 300
# Medicines analysed on first start so the Decision Center has real pending recommendations.
# Amoxicillin is deliberately left for the live demo, where the manager triggers the analysis.
BOOTSTRAP_MEDICINES = ["MED-005", "MED-004", "MED-006"]
# Each analysis makes two LLM calls (~4-5k tokens); spacing keeps first start inside Groq free-tier minute limits.
BOOTSTRAP_SPACING_SECONDS = 30


def scan_inventory() -> int:
    """Flag medicines entering high/critical risk that have no active decision (once per 12 hours)."""
    flagged = 0
    since = (datetime.now() - timedelta(hours=12)).isoformat()
    for item in inventory.list_inventory():
        if item["risk_level"] not in ("CRITICAL", "HIGH") or item["active_decision_id"]:
            continue
        recent = db.query_one("SELECT 1 AS x FROM events WHERE kind = 'detect' AND medicine_id = ? AND ts >= ?",
                              (item["id"], since))
        if recent:
            continue
        log_event("detect", f"Risk scan flagged {item['risk_level'].lower()} stock-out risk",
                  f"{item['name']} · {item['days_remaining']:g} days of cover — awaiting agent analysis", item["id"],
                  meta={"risk_level": item["risk_level"], "days_remaining": item["days_remaining"], "trigger": "scan"})
        flagged += 1
    return flagged


async def bootstrap() -> None:
    if settings.llm_configured:
        status = await llm.ping()
        if status["error"]:
            log_event("error", "LLM check failed — the agent will use its deterministic engine", status["error"])
    if settings.hindsight_configured:
        await memory_service.seed_memory()
    if db.get_setting("bootstrap_done") == "1":
        return
    if not (settings.hindsight_configured and memory_service.seed_state["state"] == "done"):
        return  # analyse only once real memory is available
    for medicine_id in BOOTSTRAP_MEDICINES:
        try:
            await inventory_agent.analyze(medicine_id, trigger="startup")
        except Exception as exc:  # noqa: BLE001
            log.warning("Bootstrap analysis failed for %s: %s", medicine_id, exc)
        await asyncio.sleep(BOOTSTRAP_SPACING_SECONDS)
    db.set_setting("bootstrap_done", "1")


async def run_forever() -> None:
    try:
        await bootstrap()
    except Exception as exc:  # noqa: BLE001
        log.warning("Bootstrap failed: %s", exc)
    while True:
        try:
            scan_inventory()
        except Exception as exc:  # noqa: BLE001
            log.warning("Inventory scan failed: %s", exc)
        await asyncio.sleep(SCAN_INTERVAL_SECONDS)
