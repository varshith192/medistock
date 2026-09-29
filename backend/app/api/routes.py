"""HTTP API."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.agents import inventory_agent, llm
from app.agents.inventory_agent import AgentError
from app.config import settings
from app.database import db
from app.hindsight import client as hs
from app.models.schemas import (AnalyzeRequest, ApproveRequest, DemoRunRequest, HealthResponse, OutcomeRequest,
                                RecallRequest, RejectRequest, SettingsUpdate)
from app.services import demo, inventory, memory_service, overview, risk
from app.services.events import recent_events

router = APIRouter(prefix="/api")


def _agent_error(exc: AgentError) -> HTTPException:
    message = str(exc)
    code = 404 if "not found" in message else 409
    return HTTPException(status_code=code, detail=message)


# ── system ───────────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def health() -> dict[str, Any]:
    try:
        n = db.query_one("SELECT COUNT(*) AS n FROM medicines")["n"]
        database = {"ok": True, "medicines": n, "path": str(settings.database_path.name)}
    except Exception as exc:  # noqa: BLE001
        database = {"ok": False, "error": str(exc)}
    if settings.hindsight_configured:
        hind = await hs.check_health()
    else:
        hind = {"connected": False, "error": "HINDSIGHT_API_KEY is not set in backend/.env"}
    hind.update(bank_id=settings.hindsight_bank_id, base_url=settings.hindsight_base_url,
                configured=settings.hindsight_configured, seed=memory_service.seed_state)
    agent = {"configured": settings.llm_configured, "model": settings.groq_model, "provider": "Groq",
             "ok": llm.status["ok"] if settings.llm_configured else False,
             "error": llm.status["error"] if settings.llm_configured else "GROQ_API_KEY is not set in backend/.env"}
    return {"database": database, "agent": agent, "hindsight": hind}


@router.get("/events")
def events(limit: int = 30, kinds: str | None = None) -> list[dict[str, Any]]:
    return recent_events(min(limit, 200), kinds.split(",") if kinds else None)


@router.get("/settings")
def get_settings() -> dict[str, Any]:
    return {"expiry_threshold_days": risk.expiry_threshold_days(), "target_cover_days": risk.target_cover_days(),
            "risk_rules": {"CRITICAL": "≤ 2 days", "HIGH": "2–4 days", "MEDIUM": "4–7 days", "LOW": "> 7 days"},
            "llm_model": settings.groq_model, "hindsight_base_url": settings.hindsight_base_url,
            "hindsight_bank_id": settings.hindsight_bank_id}


@router.put("/settings")
def put_settings(body: SettingsUpdate) -> dict[str, Any]:
    if body.expiry_threshold_days is not None:
        db.set_setting("expiry_threshold_days", str(body.expiry_threshold_days))
    if body.target_cover_days is not None:
        db.set_setting("target_cover_days", str(body.target_cover_days))
    return get_settings()


# ── inventory ────────────────────────────────────────────────────────────────

@router.get("/overview")
def get_overview() -> dict[str, Any]:
    return overview.overview()


@router.get("/inventory")
def get_inventory() -> list[dict[str, Any]]:
    return inventory.list_inventory()


@router.get("/inventory/{medicine_id}")
def get_inventory_item(medicine_id: str) -> dict[str, Any]:
    detail = inventory.medicine_detail(medicine_id)
    if not detail:
        raise HTTPException(404, f"Medicine {medicine_id} not found")
    return detail


@router.get("/risks")
def get_risks() -> dict[str, Any]:
    items = inventory.list_inventory()
    return {
        "stock": sorted([i for i in items if i["risk_level"] != "LOW"], key=lambda i: i["days_remaining"]),
        "expiry": sorted([i for i in items if i["expiry_risk"]], key=lambda i: i["days_to_expiry"]),
    }


@router.get("/suppliers")
def get_suppliers() -> list[dict[str, Any]]:
    return overview.suppliers_intelligence()


@router.get("/incidents")
def get_incidents() -> list[dict[str, Any]]:
    return overview.list_incidents()


# ── agent + decisions ────────────────────────────────────────────────────────

@router.post("/agent/analyze")
async def analyze(body: AnalyzeRequest) -> dict[str, Any]:
    try:
        return await inventory_agent.analyze(body.medicine_id)
    except AgentError as exc:
        raise _agent_error(exc) from exc


@router.get("/decisions")
def decisions(status: str | None = None, medicine_id: str | None = None) -> list[dict[str, Any]]:
    return inventory_agent.list_decisions(status, medicine_id)


@router.get("/decisions/{decision_id}")
def decision(decision_id: str) -> dict[str, Any]:
    try:
        return inventory_agent.get_decision(decision_id)
    except AgentError as exc:
        raise _agent_error(exc) from exc


@router.post("/decisions/{decision_id}/approve")
def approve(decision_id: str, body: ApproveRequest) -> dict[str, Any]:
    try:
        return inventory_agent.record_manager_decision(decision_id, body.supplier_id, body.quantity, body.note)
    except AgentError as exc:
        raise _agent_error(exc) from exc


@router.post("/decisions/{decision_id}/reject")
async def reject(decision_id: str, body: RejectRequest) -> dict[str, Any]:
    try:
        return await inventory_agent.reject_decision(decision_id, body.reason)
    except AgentError as exc:
        raise _agent_error(exc) from exc


@router.post("/decisions/{decision_id}/outcome")
async def outcome(decision_id: str, body: OutcomeRequest) -> dict[str, Any]:
    try:
        return await inventory_agent.record_outcome(decision_id, body.delivered_quantity, body.delivery_days,
                                                    body.stockout_occurred, body.notes)
    except AgentError as exc:
        raise _agent_error(exc) from exc


@router.post("/decisions/{decision_id}/retain")
async def retry_retain(decision_id: str) -> dict[str, Any]:
    try:
        await inventory_agent.retain_outcome(decision_id)
        return inventory_agent.get_decision(decision_id)
    except AgentError as exc:
        raise _agent_error(exc) from exc


# ── memory ───────────────────────────────────────────────────────────────────

def _require_hindsight() -> None:
    if not settings.hindsight_configured:
        raise HTTPException(503, "Hindsight is not configured. Set HINDSIGHT_API_KEY in backend/.env and restart.")


@router.get("/memory")
async def memory() -> dict[str, Any]:
    _require_hindsight()
    try:
        return await memory_service.memory_overview()
    except Exception as exc:  # noqa: BLE001
        hs.mark(False, exc)
        raise HTTPException(502, f"Hindsight request failed: {hs._describe(exc)}") from exc


@router.post("/memory/recall")
async def memory_recall(body: RecallRequest) -> dict[str, Any]:
    _require_hindsight()
    try:
        return await memory_service.explore(body.query)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Hindsight recall failed: {hs._describe(exc)}") from exc


@router.post("/memory/seed")
async def memory_seed() -> dict[str, Any]:
    _require_hindsight()
    await memory_service.seed_memory()
    return memory_service.seed_state


# ── demo ─────────────────────────────────────────────────────────────────────


@router.post("/demo/run")
def demo_run(body: DemoRunRequest) -> dict[str, Any]:
    try:
        if body.action == "new_situation":
            return demo.new_situation(body.medicine_id)
        return demo.prepare_scenario()
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/demo/reset")
async def demo_reset() -> dict[str, Any]:
    return await demo.reset_all()
