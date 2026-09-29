"""Turn raw Hindsight results into structured operational memory items."""
from __future__ import annotations

from typing import Any

CATEGORY_LABELS = {
    "supplier_knowledge": "Supplier Knowledge",
    "medicine_pattern": "Medicine Patterns",
    "stock_out_incident": "Stock-Out Incidents",
    "replenishment_decision": "Replenishment Decisions",
    "expiry_incident": "Expiry Incidents",
    "manager_feedback": "Manager Feedback",
    "successful_outcome": "Successful Outcomes",
}


def tag_value(tags: list[str] | None, prefix: str) -> str | None:
    for tag in tags or []:
        if tag.startswith(prefix + ":"):
            return tag.split(":", 1)[1]
    return None


def category_of(tags: list[str] | None, metadata: dict[str, Any] | None) -> str:
    return (metadata or {}).get("category") or tag_value(tags, "category") or "supplier_knowledge"


def _dump(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if isinstance(obj, dict):
        return obj
    return dict(obj)


def parse_recall_result(result: Any, ref: str) -> dict[str, Any]:
    raw = _dump(result)
    tags = raw.get("tags") or []
    metadata = raw.get("metadata") or {}
    scores = raw.get("scores") or {}
    full_text = raw.get("text", "")
    return {
        "ref": ref,
        "id": raw.get("id"),
        # Hindsight facts read "fact | When: … | Involving: … | why"; show the fact, give the model everything.
        "text": full_text.split(" | ")[0].strip(),
        "full_text": full_text,
        "fact_type": raw.get("type"),
        "occurred_start": raw.get("occurred_start"),
        "mentioned_at": raw.get("mentioned_at"),
        "document_id": raw.get("document_id"),
        "tags": tags,
        "metadata": metadata,
        "category": category_of(tags, metadata),
        "medicine_id": metadata.get("medicine_id") or tag_value(tags, "medicine"),
        "supplier_id": metadata.get("supplier_id") or tag_value(tags, "supplier"),
        "score": scores.get("final") or scores.get("rerank") or scores.get("combined"),
        "source": "hindsight",
    }


def relevance_group(item: dict[str, Any], medicine: dict[str, Any], supplier_ids: list[str]) -> str | None:
    """'medicine' (about this medicine), 'supplier' (a candidate supplier in general), 'policy' (manager
    feedback), or None when the memory is about something else."""
    if item.get("medicine_id"):
        if item["medicine_id"] == medicine["id"]:
            return "medicine"
    elif medicine["generic_name"].lower().split(" ")[0] in item["text"].lower():
        return "medicine"
    if item["category"] == "manager_feedback" and not item.get("medicine_id"):
        return "policy"
    if item.get("supplier_id") in supplier_ids and not item.get("medicine_id"):
        return "supplier"
    return None


def delivery_evidence(items: list[dict[str, Any]], medicine_id: str) -> list[dict[str, Any]]:
    """Supplier delivery evidence carried in retained memory metadata: medicine-specific experiences, plus
    supplier-wide performance knowledge (scope 'supplier') used when a medicine has no history of its own."""
    evidence = []
    seen: set[str] = set()
    for item in items:
        meta = item.get("metadata") or {}
        if not meta.get("actual_delivery_days") or not meta.get("supplier_id"):
            continue
        if meta.get("medicine_id") == medicine_id:
            scope = "medicine"
        elif not meta.get("medicine_id"):
            scope = "supplier"
        else:
            continue
        key = item.get("document_id") or item["id"]
        if key in seen:
            continue
        seen.add(key)
        evidence.append({
            "ref": item["ref"],
            "document_id": item.get("document_id"),
            "supplier_id": meta.get("supplier_id"),
            "scope": scope,
            "actual_delivery_days": float(meta["actual_delivery_days"]),
            "expected_delivery_days": float(meta.get("expected_delivery_days") or 0) or None,
            "outcome": meta.get("outcome"),
            "occurred_on": meta.get("occurred_on"),
            "decision_id": meta.get("decision_id") or "",
        })
    return evidence