"""Recall relevant operational experience from Hindsight."""
from __future__ import annotations

import asyncio
import re
import time
from typing import Any

from app.config import settings
from app.hindsight import client as hs
from app.hindsight.memory_parser import parse_recall_result, relevance_group

# Retained documents are immutable in this app, so their metadata can be cached per document id.
_document_meta: dict[str, dict[str, Any]] = {}


def build_query(medicine: dict[str, Any], suppliers: list[dict[str, Any]]) -> str:
    names = ", ".join(s["name"] for s in suppliers)
    return (
        f"{medicine['name']} ({medicine['generic_name']}) replenishment: past stock-out incidents, supplier "
        f"delivery delays, actual vs expected lead times, previous replenishment decisions and their outcomes, "
        f"manager feedback. Suppliers: {names}."
    )


async def _document_metadata(document_id: str) -> dict[str, Any]:
    """Tags and metadata of the Hindsight document a recalled fact was extracted from."""
    if document_id not in _document_meta:
        doc = await hs.get_client().documents.get_document(bank_id=settings.hindsight_bank_id,
                                                           document_id=document_id)
        raw = doc.to_dict() if hasattr(doc, "to_dict") else dict(doc)
        _document_meta[document_id] = {"tags": raw.get("tags") or [], "metadata": raw.get("document_metadata") or {}}
    return _document_meta[document_id]


async def _enrich(results: list[Any]) -> None:
    """Facts may not carry their document's metadata; attach it from the source document."""
    doc_ids = {r.document_id for r in results if getattr(r, "document_id", None)}
    missing = [d for d in doc_ids if d not in _document_meta]
    if missing:
        await asyncio.gather(*(_document_metadata(d) for d in missing), return_exceptions=True)
    for r in results:
        source = _document_meta.get(getattr(r, "document_id", None) or "")
        if not source:
            continue
        r.metadata = {**{k: str(v) for k, v in source["metadata"].items()}, **(r.metadata or {})}
        r.tags = sorted(set(r.tags or []) | set(source["tags"]))


def forget_document(document_id: str) -> None:
    _document_meta.pop(document_id, None)


async def recall(query: str, max_results: int = 12, budget: str = "mid") -> dict[str, Any]:
    started = time.perf_counter()

    async def run() -> Any:
        await hs.ensure_bank()
        response = await hs.get_client().arecall(
            bank_id=settings.hindsight_bank_id, query=query, budget=budget, max_tokens=3000)
        await _enrich(response.results[:max_results])
        return response

    try:
        response = await asyncio.wait_for(run(), timeout=hs.RECALL_TIMEOUT_SECONDS)
        hs.mark(True)
    except asyncio.TimeoutError as exc:
        error = TimeoutError(f"Hindsight recall did not respond within {hs.RECALL_TIMEOUT_SECONDS:g}s")
        hs.mark(False, error)
        raise error from exc
    except Exception as exc:
        hs.mark(False, exc)
        raise
    items = [parse_recall_result(r, f"M{i + 1}") for i, r in enumerate(response.results[:max_results])]
    return {"query": query, "items": items, "duration_ms": round((time.perf_counter() - started) * 1000),
            "total_results": len(response.results)}


async def recall_for_medicine(medicine: dict[str, Any], suppliers: list[dict[str, Any]]) -> dict[str, Any]:
    """Recall, then keep the memories that matter for this decision."""
    query = build_query(medicine, suppliers)
    result = await recall(query, max_results=40)
    selected = select_relevant(result["items"], medicine, [s["id"] for s in suppliers])
    for i, item in enumerate(selected):
        item["ref"] = f"M{i + 1}"
    return {**result, "items": selected}


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9.]+", text.lower()) if len(t) > 2}


def select_relevant(items: list[dict[str, Any]], medicine: dict[str, Any], supplier_ids: list[str],
                    limit: int = 10) -> list[dict[str, Any]]:
    """Experience about this medicine first (one fact per experience before any second fact), then at most two
    supplier-wide and two policy memories. Near-duplicates (a consolidated observation restating a fact) are
    dropped so repeated policies cannot crowd out the medicine's own history."""
    unique: list[dict[str, Any]] = []
    for item in items:
        tokens = _tokens(item["text"])
        doc = item.get("document_id")
        # Only a restatement of the same experience is a duplicate; similar wording from a different
        # experience (e.g. two outcomes written from the same template) is new evidence and stays.
        if any((not doc or doc == u.get("document_id"))
               and len(tokens & _tokens(u["text"])) / max(len(tokens | _tokens(u["text"])), 1) >= 0.6
               for u in unique):
            continue
        unique.append(item)
    groups: dict[str | None, list[dict[str, Any]]] = {"medicine": [], "supplier": [], "policy": [], None: []}
    for item in unique:
        groups[relevance_group(item, medicine, supplier_ids)].append(item)
    specific = _diversify(groups["medicine"], len(groups["medicine"]))
    selected = specific[:limit - 4] + groups["supplier"][:2] + groups["policy"][:2]
    selected += specific[limit - 4:][: max(0, limit - len(selected))]
    return selected[:limit]


def _diversify(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Best-ranked fact from each distinct experience first, then the remaining facts in rank order.

    Hindsight ranks individual facts; without this, one detailed experience can fill every slot and hide a
    more recent experience about the same medicine.
    """
    firsts, observations, rest, seen = [], [], [], set()
    for item in items:
        doc = item.get("document_id")
        if not doc:  # consolidated observations: after each retained experience has one slot
            observations.append(item)
            continue
        (rest if doc in seen else firsts).append(item)
        seen.add(doc)
    return (firsts + observations + rest)[:limit]