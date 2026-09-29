"""Retain operational experiences into Hindsight."""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.database import db
from app.hindsight import client as hs
from app.hindsight.recall import forget_document
from app.services.events import log_event


async def retain_experience(
    *,
    document_id: str,
    content: str,
    context: str,
    category: str,
    origin: str,
    timestamp: datetime | None = None,
    medicine_id: str | None = None,
    supplier_id: str | None = None,
    metadata: dict[str, str] | None = None,
    decision_id: str | None = None,
    log: bool = True,
) -> dict[str, Any]:
    """Store one distilled experience in Hindsight and register it locally.

    Raises on failure so callers can surface the error; nothing is marked as retained
    unless Hindsight accepted it.
    """
    tags = [f"category:{category}", f"origin:{origin}"]
    if medicine_id:
        tags.append(f"medicine:{medicine_id}")
    if supplier_id:
        tags.append(f"supplier:{supplier_id}")
    meta = {k: str(v) for k, v in (metadata or {}).items() if v is not None}
    meta.update({"category": category, "medicine_id": medicine_id or "", "origin": origin})

    started = time.perf_counter()
    try:
        await hs.ensure_bank()
        response = await asyncio.wait_for(hs.get_client().aretain(
            bank_id=settings.hindsight_bank_id,
            content=content,
            context=context,
            timestamp=timestamp or datetime.now(timezone.utc),
            document_id=document_id,
            metadata=meta,
            tags=tags,
            retain_async=False,
        ), timeout=hs.RETAIN_TIMEOUT_SECONDS)
        hs.mark(True)
        forget_document(document_id)  # a re-retained document may carry new metadata
    except Exception as exc:
        if isinstance(exc, asyncio.TimeoutError):
            exc = TimeoutError(f"Hindsight retain did not complete within {hs.RETAIN_TIMEOUT_SECONDS:g}s")
        hs.mark(False, exc)
        if log:
            log_event("error", "Hindsight retain failed", hs._describe(exc), medicine_id, decision_id,
                      {"document_id": document_id})
        raise

    duration_ms = round((time.perf_counter() - started) * 1000)
    info = {
        "document_id": document_id,
        "bank_id": response.bank_id,
        "items_count": response.items_count,
        "operation_id": response.operation_id,
        "duration_ms": duration_ms,
        "tags": tags,
    }
    db.insert("memory_registry", {
        "document_id": document_id, "origin": origin, "category": category, "medicine_id": medicine_id,
        "retained_at": datetime.now().isoformat(timespec="seconds"), "items_count": response.items_count,
    })
    if log:
        log_event("retain", "Hindsight retain — new operational experience stored",
                  f"{context} · document {document_id}", medicine_id, decision_id, info)
    return info


async def delete_document(document_id: str) -> None:
    await hs.get_client().documents.delete_document(bank_id=settings.hindsight_bank_id, document_id=document_id)
    forget_document(document_id)
    db.execute("DELETE FROM memory_registry WHERE document_id = ?", (document_id,))
