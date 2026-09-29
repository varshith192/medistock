"""Hindsight-compatible test server used ONLY by the test suite.

It implements the REST routes the official `hindsight-client` SDK calls (bank upsert, retain,
recall, documents, memory listing) so the application's real integration code paths run
end-to-end without cloud credentials. Recall ranking is simple keyword overlap.

Deliberately pessimistic: extracted facts do NOT carry their document's tags/metadata, so the
tests prove the app enriches recalled facts from their source document.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import Body, FastAPI, HTTPException

app = FastAPI()
DOCS: dict[str, dict[str, Any]] = {}
FACTS: list[dict[str, Any]] = []
STOP = {"the", "a", "an", "of", "and", "or", "to", "in", "for", "on", "with", "was", "is", "by", "at", "vs"}


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9.]+", text.lower()) if t not in STOP and len(t) > 1}


def reset() -> None:
    DOCS.clear()
    FACTS.clear()


@app.put("/v1/default/banks/{bank_id}")
def upsert_bank(bank_id: str, body: dict = Body(default={})) -> dict:
    return {"bank_id": bank_id, "name": body.get("name") or bank_id, "mission": body.get("mission") or "",
            "disposition": {"skepticism": 3, "literalism": 3, "empathy": 3}}


@app.post("/v1/default/banks/{bank_id}/memories")
def retain(bank_id: str, body: dict = Body(...)) -> dict:
    for item in body["items"]:
        doc_id = item.get("document_id") or str(uuid.uuid4())
        FACTS[:] = [f for f in FACTS if f["document_id"] != doc_id]
        now = datetime.now(timezone.utc).isoformat()
        sentences = [s.strip() for s in re.split(r"(?<=\.)\s+", item["content"]) if len(s.strip()) > 20]
        for s in sentences:
            FACTS.append({"id": str(uuid.uuid4()), "text": s, "type": "world", "document_id": doc_id,
                          "occurred_start": item.get("timestamp"), "mentioned_at": now, "context": item.get("context")})
        DOCS[doc_id] = {"id": doc_id, "bank_id": bank_id, "original_text": item["content"], "content_hash": "x",
                        "created_at": now, "updated_at": now, "memory_unit_count": len(sentences),
                        "tags": item.get("tags") or [], "document_metadata": item.get("metadata") or {}}
    return {"success": True, "bank_id": bank_id, "items_count": len(body["items"]), "async": False}


@app.post("/v1/default/banks/{bank_id}/memories/recall")
def recall(bank_id: str, body: dict = Body(...)) -> dict:
    q = _tokens(body["query"])
    scored = sorted(((len(q & _tokens(f["text"])), f) for f in FACTS), key=lambda x: -x[0])
    return {"results": [{k: v for k, v in f.items() if k != "context"} for score, f in scored if score > 0][:30]}


@app.get("/v1/default/banks/{bank_id}/documents")
def list_documents(bank_id: str, limit: int = 100, offset: int = 0) -> dict:
    items = [{k: v for k, v in d.items() if k not in ("original_text", "content_hash")} for d in DOCS.values()]
    return {"items": items[offset:offset + limit], "total": len(items), "limit": limit, "offset": offset}


@app.get("/v1/default/banks/{bank_id}/documents/{document_id}")
def get_document(bank_id: str, document_id: str) -> dict:
    if document_id not in DOCS:
        raise HTTPException(404, "Document not found")
    return DOCS[document_id]


@app.delete("/v1/default/banks/{bank_id}/documents/{document_id}")
def delete_document(bank_id: str, document_id: str) -> dict:
    doc = DOCS.pop(document_id, None)
    if not doc:
        raise HTTPException(404, "Document not found")
    before = len(FACTS)
    FACTS[:] = [f for f in FACTS if f["document_id"] != document_id]
    return {"success": True, "message": "deleted", "document_id": document_id, "memory_units_deleted": before - len(FACTS)}


@app.get("/v1/default/banks/{bank_id}/memories/list")
def list_memories(bank_id: str, limit: int = 100, offset: int = 0) -> dict:
    items = [{"id": f["id"], "text": f["text"], "context": f["context"] or "", "date": f["occurred_start"] or "",
              "fact_type": f["type"], "document_id": f["document_id"], "mentioned_at": f["mentioned_at"]}
             for f in FACTS]
    return {"items": items[offset:offset + limit], "total": len(items), "limit": limit, "offset": offset}
