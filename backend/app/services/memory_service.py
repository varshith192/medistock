"""Operational memory read-side (everything here is read from Hindsight) and seed/bootstrap."""
from __future__ import annotations

import asyncio
from collections import Counter
from typing import Any

from app.config import settings
from app.database import db
from app.hindsight import client as hs
from app.hindsight.memory_parser import CATEGORY_LABELS, category_of, tag_value
from app.hindsight.recall import recall
from app.hindsight.retain import retain_experience
from app.seed.memory_seed import seed_experiences
from app.services.events import log_event

seed_state: dict[str, Any] = {"state": "idle", "done": 0, "total": 0, "error": None, "current": None}


_document_details: dict[tuple[str, str | None], dict[str, Any]] = {}


def _dump(obj: Any) -> dict[str, Any]:
    return obj.to_dict() if hasattr(obj, "to_dict") else dict(obj)


async def list_hindsight_documents() -> list[dict[str, Any]]:
    client = hs.get_client()
    await hs.ensure_bank()
    response = await client.documents.list_documents(bank_id=settings.hindsight_bank_id, limit=200)
    return [_dump(item) for item in response.items]


async def memory_overview() -> dict[str, Any]:
    """Documents (retained experiences) with the facts Hindsight extracted from each."""
    client = hs.get_client()
    await hs.ensure_bank()
    listing, facts_response = await asyncio.gather(
        client.documents.list_documents(bank_id=settings.hindsight_bank_id, limit=200),
        client.alist_memories(bank_id=settings.hindsight_bank_id, limit=500),
    )
    documents = [_dump(item) for item in listing.items]
    # Full document text only changes when a document is rewritten, so cache it per (id, updated_at).
    missing = [doc for doc in documents if (doc["id"], doc.get("updated_at")) not in _document_details]
    fetched = await asyncio.gather(*[client.documents.get_document(bank_id=settings.hindsight_bank_id,
                                                                   document_id=doc["id"]) for doc in missing])
    for doc, detail in zip(missing, fetched):
        _document_details[(doc["id"], doc.get("updated_at"))] = _dump(detail)
    details = [_document_details[(doc["id"], doc.get("updated_at"))] for doc in documents]
    hs.mark(True)
    facts_by_doc: dict[str, list[dict[str, Any]]] = {}
    fact_types: Counter[str] = Counter()
    for unit in facts_response.items:
        u = _dump(unit)
        fact_types[u.get("fact_type") or "unknown"] += 1
        if u.get("document_id"):
            facts_by_doc.setdefault(u["document_id"], []).append({
                "id": u["id"], "text": u.get("text"), "fact_type": u.get("fact_type"),
                "occurred_start": u.get("occurred_start"), "mentioned_at": u.get("mentioned_at"),
                "entities": u.get("entities"), "proof_count": u.get("proof_count"),
            })
    medicines = {m["id"]: m["name"] for m in db.query("SELECT id, name FROM medicines")}
    suppliers = {s["id"]: s["name"] for s in db.query("SELECT id, name FROM suppliers")}
    registry = {r["document_id"]: r for r in db.query("SELECT * FROM memory_registry")}

    cards = []
    for doc, detail in zip(documents, details):
        full = _dump(detail)
        tags = full.get("tags") or doc.get("tags") or []
        meta = full.get("document_metadata") or doc.get("document_metadata") or {}
        category = category_of(tags, meta)
        medicine_id = meta.get("medicine_id") or tag_value(tags, "medicine")
        supplier_id = meta.get("supplier_id") or tag_value(tags, "supplier")
        cards.append({
            "document_id": doc["id"],
            "category": category,
            "category_label": CATEGORY_LABELS.get(category, category.replace("_", " ").title()),
            "origin": tag_value(tags, "origin") or registry.get(doc["id"], {}).get("origin") or "external",
            "medicine_id": medicine_id or None,
            "medicine_name": medicines.get(medicine_id or ""),
            "supplier_id": supplier_id,
            "supplier_name": suppliers.get(supplier_id or ""),
            "occurred_on": meta.get("occurred_on"),
            "outcome": meta.get("outcome"),
            "actual_delivery_days": meta.get("actual_delivery_days"),
            "expected_delivery_days": meta.get("expected_delivery_days"),
            "created_at": full.get("created_at") or doc.get("created_at"),
            "memory_unit_count": full.get("memory_unit_count") or doc.get("memory_unit_count") or 0,
            "original_text": full.get("original_text"),
            "tags": tags,
            "facts": facts_by_doc.get(doc["id"], []),
        })
    cards.sort(key=lambda c: (c["occurred_on"] or c["created_at"] or ""), reverse=True)
    counts = Counter(c["category"] for c in cards)
    return {
        "bank_id": settings.hindsight_bank_id,
        "base_url": settings.hindsight_base_url,
        "documents": cards,
        "totals": {"documents": len(cards), "facts": facts_response.total, "fact_types": dict(fact_types)},
        "categories": [{"key": k, "label": v, "count": counts.get(k, 0)} for k, v in CATEGORY_LABELS.items()],
    }


async def explore(query: str) -> dict[str, Any]:
    result = await recall(query, max_results=12)
    log_event("recall", f"Hindsight recall — {len(result['items'])} memories found",
              f"Memory explorer · \"{query[:80]}\"", meta={"count": len(result["items"]),
                                                          "duration_ms": result["duration_ms"]})
    return result


# ── seed + bootstrap ─────────────────────────────────────────────────────────

def sync_incident_memory_status() -> None:
    retained = {r["document_id"] for r in db.query("SELECT document_id FROM memory_registry")}
    for inc in db.query("SELECT id, memory_document_id, memory_status FROM incidents WHERE memory_document_id IS NOT NULL"):
        if inc["memory_document_id"] in retained and inc["memory_status"] != "retained":
            db.update("incidents", "id", inc["id"], {"memory_status": "retained"})


async def seed_memory() -> None:
    """Retain the historical experiences into Hindsight (skips ones already in the bank)."""
    if seed_state["state"] == "running":
        return
    experiences = seed_experiences()
    seed_state.update(state="running", done=0, total=len(experiences), error=None, current=None)
    try:
        existing = {d["id"] for d in await list_hindsight_documents()}
        for exp in experiences:
            seed_state["current"] = exp["document_id"]
            if exp["document_id"] in existing:
                if not db.query_one("SELECT 1 AS x FROM memory_registry WHERE document_id = ?", (exp["document_id"],)):
                    db.insert("memory_registry", {"document_id": exp["document_id"], "origin": "seed",
                                                  "category": exp["category"], "medicine_id": exp["medicine_id"],
                                                  "retained_at": exp["timestamp"].isoformat(), "items_count": 1})
            else:
                await retain_experience(
                    document_id=exp["document_id"], content=exp["content"], context=exp["context"],
                    category=exp["category"], origin="seed", timestamp=exp["timestamp"],
                    medicine_id=exp["medicine_id"], supplier_id=exp["supplier_id"], metadata=exp["metadata"],
                    log=False)
            seed_state["done"] += 1
            sync_incident_memory_status()
        log_event("retain", "Historical operational experience loaded into Hindsight",
                  f"{len(experiences)} experiences in bank {settings.hindsight_bank_id}",
                  meta={"count": len(experiences)})
        seed_state.update(state="done", current=None)
    except Exception as exc:  # noqa: BLE001
        seed_state.update(state="error", error=hs._describe(exc), current=None)
        log_event("error", "Hindsight memory seeding failed", hs._describe(exc))
