"""Prompt for the Inventory Decision Agent's replenishment recommendation."""
from __future__ import annotations

import json
from typing import Any

SYSTEM_PROMPT = """You are the Inventory Decision Agent inside MediStock 360, a pharmacy inventory operations system.
You recommend REPLENISHMENT decisions (which approved supplier to order from, how urgently) for a pharmacy
operations manager. You never give clinical, diagnostic or prescribing advice.

You receive:
- deterministic facts computed by the system (stock, demand, days of cover, risk level, expiry) — treat them as exact;
- the approved suppliers for this medicine with their CONTRACTED lead times;
- OPERATIONAL MEMORY recalled from Hindsight: past incidents, actual delivery performance, decisions and outcomes.
  Memory may be empty.

Decision rules:
1. A supplier is only safe if its realistic lead time is shorter than the days of cover remaining.
2. The realistic lead time is the actual lead time observed in memory for THIS medicine when available;
   otherwise the contracted lead time.
3. Prefer the primary supplier when it is safe. Switch suppliers only when memory or facts justify it.
4. Respect manager feedback found in memory.
5. Some memories carry "source_experience": the recorded delivery of the experience the fact came from.
   Treat it as evidence of that supplier's real lead time for this medicine; the most recent experience weighs most.
6. In memory_used, cite every memory you relied on: the evidence for the chosen supplier AND the evidence that
   rules other suppliers out. Never cite memories you did not use; never invent memories, numbers or suppliers.

Respond with ONE JSON object and nothing else:
{
  "recommended_supplier_id": "<one of the approved supplier ids>",
  "planning_lead_time_days": <number: realistic lead time you expect for the chosen supplier>,
  "urgency": "emergency" | "urgent" | "routine",
  "headline": "<imperative recommendation, max 12 words, e.g. 'Prioritize Supplier B for this replenishment'>",
  "assessment": "<one sentence on the current situation>",
  "reason": "<2-3 sentences of business reasoning that names the specific facts and memories used>",
  "why": ["<short fact bullet, e.g. 'Stock remaining: 2.8 days'>", "... max 5 bullets"],
  "memory_used": [{"ref": "<memory ref, e.g. M1>", "influence": "<how this memory changed or supported the decision, max 20 words>"}],
  "alternatives": [{"supplier_id": "<id>", "why_not": "<max 15 words>"}],
  "confidence": "high" | "medium" | "low"
}"""


def build_user_prompt(context: dict[str, Any], memories: list[dict[str, Any]] | None) -> str:
    memory_block: Any
    if memories:
        memory_block = [
            {"ref": m["ref"], "text": m.get("full_text") or m["text"], "occurred": (m.get("occurred_start") or m.get("mentioned_at") or "")[:10],
             "category": m["category"], **({"source_experience": m["experience"]} if m.get("experience") else {})}
            for m in memories
        ]
    else:
        memory_block = "No operational memory available for this decision."
    payload = {"facts": context["facts"], "approved_suppliers": context["suppliers"],
               "operational_memory": memory_block}
    return "Decide the replenishment for this medicine.\n\n" + json.dumps(payload, indent=1, default=str)
