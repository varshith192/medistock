"""Hindsight client wrapper: connection, bank setup and health.

Uses the official `hindsight-client` SDK (async variants) against Hindsight Cloud or a
self-hosted Hindsight server, depending on HINDSIGHT_BASE_URL.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from hindsight_client import Hindsight

from app.config import settings

BANK_NAME = "MediStock 360 — Pharmacy Operations Memory"
BANK_MISSION = (
    "Operational memory for a pharmacy inventory team. Remember stock-out incidents, supplier delivery "
    "performance (expected vs actual lead times), replenishment decisions and the reasons behind them, "
    "outcomes of those decisions, expiry incidents, demand patterns and manager feedback, so that future "
    "replenishment decisions are better. This is operational inventory data only; there is no patient data."
)
RETAIN_MISSION = (
    "Extract durable operational facts: which medicine, which supplier, contracted vs actual delivery days, "
    "stock level and days of cover at the time, what decision was taken and why, the outcome (successful, "
    "delayed, stock-out, write-off) and the lesson learned. Keep numbers and dates exact."
)

HEALTH_TIMEOUT_SECONDS = 8.0
RECALL_TIMEOUT_SECONDS = 45.0  # a cold Hindsight Cloud recall has taken ~18 s
RETAIN_TIMEOUT_SECONDS = 150.0  # synchronous retain includes Hindsight's fact extraction

_clients: dict[int, Hindsight] = {}
_bank_ready: set[int] = set()
status: dict[str, Any] = {"connected": False, "checked_at": None, "latency_ms": None, "error": None}


class HindsightUnavailable(RuntimeError):
    pass


def get_client() -> Hindsight:
    """One SDK client per event loop (the SDK's HTTP session is loop-bound)."""
    if not settings.hindsight_configured:
        raise HindsightUnavailable("Hindsight is not configured. Set HINDSIGHT_API_KEY in backend/.env.")
    loop_id = id(asyncio.get_running_loop())
    if loop_id not in _clients:
        _clients[loop_id] = Hindsight(base_url=settings.hindsight_base_url,
                                      api_key=settings.hindsight_api_key or None,
                                      timeout=120.0, max_attempts=2)
    return _clients[loop_id]


async def ensure_bank() -> None:
    loop_id = id(asyncio.get_running_loop())
    if loop_id in _bank_ready:
        return
    client = get_client()
    await client.acreate_bank(
        bank_id=settings.hindsight_bank_id,
        name=BANK_NAME,
        mission=BANK_MISSION,
        retain_mission=RETAIN_MISSION,
    )
    _bank_ready.add(loop_id)


async def check_health(max_age_seconds: float = 15.0) -> dict[str, Any]:
    if status["checked_at"] and time.time() - status["checked_at"] < max_age_seconds and status["connected"]:
        return dict(status)
    started = time.perf_counter()
    try:
        client = get_client()

        async def probe() -> None:
            await ensure_bank()
            await client.documents.list_documents(bank_id=settings.hindsight_bank_id, limit=1)

        await asyncio.wait_for(probe(), timeout=HEALTH_TIMEOUT_SECONDS)
        status.update(connected=True, error=None, latency_ms=round((time.perf_counter() - started) * 1000))
    except asyncio.TimeoutError:
        status.update(connected=False, error=f"No response from Hindsight within {HEALTH_TIMEOUT_SECONDS:g}s",
                      latency_ms=None)
    except Exception as exc:  # noqa: BLE001 - surfaced to the UI as connection status
        status.update(connected=False, error=_describe(exc), latency_ms=None)
    status["checked_at"] = time.time()
    return dict(status)


def mark(ok: bool, exc: Exception | None = None) -> None:
    status["connected"] = ok
    status["error"] = None if ok else _describe(exc)
    status["checked_at"] = time.time()


def _describe(exc: Exception | None) -> str:
    if exc is None:
        return "Unknown error"
    text = str(exc).strip().splitlines()[0] if str(exc).strip() else exc.__class__.__name__
    return text[:240]
