"""Inventory Decision Agent.

Orchestrates backend tools: inventory lookup, deterministic risk, supplier terms, Hindsight recall,
LLM recommendation (with and without memory), validation, decision storage, manager decisions,
outcome recording and Hindsight retain. The LLM only proposes; the backend validates and persists.
"""
from __future__ import annotations

import asyncio
import time
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, Iterator

from app.agents import llm
from app.database import db
from app.hindsight import client as hs
from app.hindsight.memory_parser import delivery_evidence
from app.hindsight.recall import recall_for_medicine
from app.hindsight.retain import retain_experience
from app.prompts.recommendation import SYSTEM_PROMPT, build_user_prompt
from app.services import inventory, risk
from app.services.events import log_event


class AgentError(RuntimeError):
    pass


# ── helpers ──────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _next_id(table: str, prefix: str, start: int) -> str:
    rows = db.query(f"SELECT id FROM {table} WHERE id LIKE ?", (f"{prefix}-%",))
    nums = [int(r["id"].split("-")[1]) for r in rows if r["id"].split("-")[1].isdigit()]
    return f"{prefix}-{max(nums + [start - 1]) + 1}"


_TYPOGRAPHY = str.maketrans({"\u202f": " ", "\u00a0": " ", "\u2009": " ", "\u2011": "-", "\u2010": "-"})


def _clean(text: Any, limit: int) -> str:
    """Normalise model typography (narrow no-break spaces, non-breaking hyphens) and cap length."""
    return str(text or "").translate(_TYPOGRAPHY).strip()[:limit]


def _fmt_days(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


def _days(value: float) -> str:
    return f"{_fmt_days(value)} day" + ("" if _fmt_days(value) == "1" else "s")


class Trace:
    def __init__(self) -> None:
        self.steps: list[dict[str, Any]] = []

    @contextmanager
    def step(self, tool: str, label: str) -> Iterator[dict[str, Any]]:
        entry = {"tool": tool, "label": label, "summary": "", "status": "ok", "duration_ms": 0}
        started = time.perf_counter()
        try:
            yield entry
        except Exception as exc:
            entry["status"] = "error"
            entry["summary"] = entry["summary"] or str(exc)[:200]
            raise
        finally:
            entry["duration_ms"] = round((time.perf_counter() - started) * 1000)
            self.steps.append(entry)


# ── tools ────────────────────────────────────────────────────────────────────

def get_medicine_details(medicine_id: str) -> dict[str, Any]:
    med = inventory.get_medicine(medicine_id)
    if not med:
        raise AgentError(f"Medicine {medicine_id} not found")
    return med


def calculate_stock_risk(med: dict[str, Any]) -> dict[str, Any]:
    trend = risk.demand_trend(med["id"])
    return {
        "medicine": med["name"],
        "current_stock_units": med["current_stock"],
        "average_daily_demand": med["daily_demand"],
        "days_of_cover_remaining": med["days_remaining"],
        "risk_level": med["risk_level"],
        "demand_last_7_days_avg": trend["recent_avg"],
        "demand_change_vs_prior_3_weeks_pct": trend["change_pct"],
        "days_to_expiry_current_batch": med["days_to_expiry"],
        "storage": med["storage"],
        "essential_medicine": bool(med["essential"]),
    }


def get_supplier_terms(med: dict[str, Any]) -> list[dict[str, Any]]:
    return [{
        "id": s["id"], "name": s["name"], "contracted_lead_days": s["contracted_lead_days"],
        "min_order_qty": s["min_order_qty"], "is_primary": s["is_primary"],
        "open_orders_in_transit": len(s["open_orders"]),
    } for s in inventory.supplier_terms(med)]


def _realistic_leads(suppliers: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Most recent observed lead time per supplier for this medicine (from memory), else contract."""
    out = {}
    for s in suppliers:
        observed = [e for e in evidence if e["supplier_id"] == s["id"]]
        # Experience with this medicine beats the supplier's general track record.
        observed = [e for e in observed if e.get("scope", "medicine") == "medicine"] or observed
        observed.sort(key=lambda e: (e.get("occurred_on") or "", e.get("decision_id") or ""), reverse=True)
        if observed:
            out[s["id"]] = {"lead": observed[0]["actual_delivery_days"], "source": "memory", "evidence": observed[0],
                            "successes": sum(1 for e in observed if e["outcome"] == "successful")}
        else:
            out[s["id"]] = {"lead": s["contracted_lead_days"], "source": "contract", "evidence": None, "successes": 0}
    return out


def _summarise_experiences(memories: list[dict[str, Any]]) -> None:
    """Attach a one-line delivery summary from each fact's source experience (Hindsight document metadata),
    so a fact such as "manager approved 100 units from Supplier B" still carries how that delivery went."""
    names = {s["id"]: s["name"] for s in db.query("SELECT id, name FROM suppliers")}
    for m in memories:
        meta = m.get("metadata") or {}
        if not (meta.get("supplier_id") and meta.get("actual_delivery_days")):
            continue
        contract = f" vs {meta['expected_delivery_days']} contracted" if meta.get("expected_delivery_days") else ""
        outcome = f", outcome {meta['outcome'].replace('_', ' ')}" if meta.get("outcome") else ""
        when = f" ({meta['occurred_on'][:10]})" if meta.get("occurred_on") else ""
        m["experience"] = (f"{names.get(meta['supplier_id'], meta['supplier_id'])}: delivered in "
                           f"{meta['actual_delivery_days']} days{contract}{outcome}{when}")


def _urgency_for(level: str) -> str:
    return {"CRITICAL": "emergency", "HIGH": "urgent"}.get(level, "routine")


# ── deterministic fallback engine (used when the LLM is unavailable) ─────────

def _rules_recommendation(facts: dict[str, Any], suppliers: list[dict[str, Any]], memories: list[dict[str, Any]],
                          evidence: list[dict[str, Any]], use_memory: bool) -> dict[str, Any]:
    primary = next((s for s in suppliers if s["is_primary"]), suppliers[0])
    leads = _realistic_leads(suppliers, evidence if use_memory else [])
    cover = facts["days_of_cover_remaining"]
    safe = [s for s in suppliers if leads[s["id"]]["lead"] < cover]
    if leads[primary["id"]]["lead"] < cover:
        choice = primary
    elif safe:
        choice = min(safe, key=lambda s: (leads[s["id"]]["lead"], -leads[s["id"]]["successes"]))
    else:
        choice = min(suppliers, key=lambda s: leads[s["id"]]["lead"])
    lead = leads[choice["id"]]["lead"]
    medicine = facts["medicine"]
    why = [f"Stock remaining: {_fmt_days(cover)} days"]
    used: list[dict[str, Any]] = []
    if use_memory:
        for s in suppliers:
            info = leads[s["id"]]
            if info["source"] == "memory":
                why.append(f"{s['name']} historical delivery: {_fmt_days(info['lead'])} days")
                used.append({"ref": info["evidence"]["ref"],
                             "influence": f"Observed {s['name']} lead time of {_fmt_days(info['lead'])} days for {medicine}."})
    def lead_phrase(s: dict[str, Any]) -> str:
        info = leads[s["id"]]
        if info["source"] == "memory":
            return f"previously took {_days(info['lead'])} to deliver this medicine"
        return f"has a contracted lead time of {_days(info['lead'])}"

    situation = f"{medicine} has about {_days(cover)} of stock remaining."
    if not safe:
        headline = f"Order from {choice['name']} now and arrange interim cover"
        reason = (f"{situation} No approved supplier can deliver before stock runs out; {choice['name']} is the fastest "
                  f"option ({lead_phrase(choice)}). Place the order immediately and arrange interim cover.")
    elif choice["id"] != primary["id"]:
        headline = f"Prioritize {choice['name']} for this replenishment"
        reason = (f"{situation} {primary['name']} {lead_phrase(primary)}, which is longer than the remaining cover, "
                  f"while {choice['name']} {lead_phrase(choice)}. Order from {choice['name']} to reduce stock-out risk.")
    else:
        headline = f"Reorder from {choice['name']}"
        reason = (f"{situation} Place a replenishment order with the primary supplier, {choice['name']}, which "
                  f"{lead_phrase(choice)}.")
    why.append(f"Recommended supplier: {choice['name']}")
    return {
        "recommended_supplier_id": choice["id"], "planning_lead_time_days": lead,
        "urgency": _urgency_for(facts["risk_level"]), "headline": headline,
        "assessment": f"{facts['risk_level'].title()} stock-out risk with {_fmt_days(cover)} days of cover.",
        "reason": reason, "why": why[:5], "memory_used": used,
        "alternatives": [{"supplier_id": s["id"], "why_not": f"Lead time {_fmt_days(leads[s['id']]['lead'])} days"}
                         for s in suppliers if s["id"] != choice["id"]][:3],
        "confidence": "high" if used and choice["id"] != primary["id"] else "medium",
    }


# ── validation ───────────────────────────────────────────────────────────────

def _validate(raw: dict[str, Any], med: dict[str, Any], facts: dict[str, Any], suppliers: list[dict[str, Any]],
              memories: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    """Check the model's proposal against business rules. Lead time and quantity are computed here, never by the LLM."""
    by_id = {s["id"]: s for s in suppliers}
    primary = next((s for s in suppliers if s["is_primary"]), suppliers[0])
    notes: list[str] = []
    supplier_id = raw.get("recommended_supplier_id")
    if supplier_id not in by_id:
        notes.append(f"Proposed supplier '{supplier_id}' is not approved for this medicine; primary supplier used.")
        supplier_id = primary["id"]
    leads = _realistic_leads(suppliers, evidence)
    cover = facts["days_of_cover_remaining"]
    safe = [s for s in suppliers if leads[s["id"]]["lead"] < cover]
    if leads[supplier_id]["lead"] >= cover and safe and supplier_id not in {s["id"] for s in safe}:
        # The proposal would arrive after the stock runs out while a faster approved supplier exists.
        fallback = _rules_recommendation(facts, suppliers, memories, evidence, use_memory=bool(evidence))
        notes.append(f"{by_id[supplier_id]['name']}'s realistic lead time ({_fmt_days(leads[supplier_id]['lead'])} days) "
                     f"exceeds the remaining cover; switched to {by_id[fallback['recommended_supplier_id']]['name']}.")
        raw, supplier_id = fallback, fallback["recommended_supplier_id"]
    supplier = by_id[supplier_id]
    lead = leads[supplier_id]["lead"]
    urgency = raw.get("urgency") if raw.get("urgency") in ("emergency", "urgent", "routine") else _urgency_for(med["risk_level"])
    confidence = raw.get("confidence") if raw.get("confidence") in ("high", "medium", "low") else "medium"
    refs = {m["ref"]: m for m in memories}
    used = []

    def cite(m: dict[str, Any], influence: str) -> None:
        used.append({"ref": m["ref"], "influence": influence, "text": m["text"], "memory_id": m["id"],
                     "document_id": m.get("document_id"), "category": m["category"],
                     "occurred": (m.get("occurred_start") or m.get("mentioned_at") or "")[:10],
                     "experience": m.get("experience")})

    for entry in raw.get("memory_used") or []:
        if isinstance(entry, dict) and entry.get("ref") in refs and entry["ref"] not in {u["ref"] for u in used}:
            cite(refs[entry["ref"]], _clean(entry.get("influence"), 200))
    # The lead times behind the quantity and the safety check come from memory: always show those memories.
    for s in suppliers:
        info = leads[s["id"]]
        if (info["source"] != "memory" or info["evidence"]["ref"] not in refs
                or info["evidence"]["ref"] in {u["ref"] for u in used}):
            continue
        if s["id"] == supplier_id:
            cite(refs[info["evidence"]["ref"]], f"Sets {s['name']}'s realistic lead time to {_days(info['lead'])}, "
                                                f"used to plan this order.")
        elif info["lead"] >= cover:
            cite(refs[info["evidence"]["ref"]], f"{s['name']} took {_days(info['lead'])} here, longer than the "
                                                f"{_days(cover)} of cover, so it was not chosen.")
    why = [_clean(w, 120) for w in (raw.get("why") or []) if str(w).strip()][:5]
    alternatives = [{"supplier_id": a["supplier_id"], "supplier_name": by_id[a["supplier_id"]]["name"],
                     "why_not": _clean(a.get("why_not"), 140)}
                    for a in (raw.get("alternatives") or [])
                    if isinstance(a, dict) and a.get("supplier_id") in by_id and a["supplier_id"] != supplier_id][:3]
    quantity = risk.recommended_quantity(med["current_stock"], med["daily_demand"], lead, med["pack_size"],
                                         supplier["min_order_qty"])
    return {
        "supplier_id": supplier_id, "supplier_name": supplier["name"], "lead_days": round(lead, 1),
        "quantity": quantity, "urgency": urgency, "confidence": confidence,
        "headline": _clean(raw.get("headline") or f"Reorder from {supplier['name']}", 140),
        "assessment": _clean(raw.get("assessment"), 300),
        "reason": _clean(raw.get("reason"), 900), "why": why, "memory_used": used,
        "alternatives": alternatives, "validation_notes": notes,
        "arrives_before_stockout": lead < cover, "lead_source": leads[supplier_id]["source"],
    }


# ── analysis ─────────────────────────────────────────────────────────────────

async def analyze(medicine_id: str, trigger: str = "manual") -> dict[str, Any]:
    in_transit = db.query_one("SELECT id, order_id FROM decisions WHERE medicine_id = ? AND status = 'approved'",
                              (medicine_id,))
    if in_transit:
        raise AgentError(f"An approved replenishment ({in_transit['id']}, order {in_transit['order_id']}) is already in "
                         f"transit for this medicine. Record its delivery outcome before analysing again.")
    trace = Trace()
    with trace.step("get_medicine_details", "Inspect inventory record") as s:
        med = get_medicine_details(medicine_id)
        s["summary"] = f"{med['current_stock']} units on hand, {_fmt_days(med['daily_demand'])} units/day average demand"

    with trace.step("calculate_stock_risk", "Calculate stock risk") as s:
        facts = calculate_stock_risk(med)
        s["summary"] = f"{_fmt_days(med['days_remaining'])} days of cover → {med['risk_level']} risk"
    log_event("detect", f"Agent detected {med['risk_level'].lower()} stock-out risk",
              f"{med['name']} · {_fmt_days(med['days_remaining'])} days of cover", med["id"],
              meta={"risk_level": med["risk_level"], "days_remaining": med["days_remaining"], "trigger": trigger})

    with trace.step("get_supplier_terms", "Inspect approved suppliers") as s:
        suppliers = get_supplier_terms(med)
        s["summary"] = ", ".join(f"{x['name']} ({_fmt_days(x['contracted_lead_days'])}d contract)" for x in suppliers)

    memories: list[dict[str, Any]] = []
    recall_query = None
    memory_state = "unavailable"
    with trace.step("recall_hindsight_memory", "Recall operational memory (Hindsight)") as s:
        try:
            recalled = await recall_for_medicine(med, suppliers)
            memories = recalled["items"]
            recall_query = recalled["query"]
            memory_state = "found" if memories else "none_found"
            s["summary"] = (f"{len(memories)} relevant memories found "
                            f"({recalled['total_results']} recalled, {recalled['duration_ms']} ms)")
            log_event("recall", f"Hindsight recall — {len(memories)} relevant memories found",
                      f"{med['name']} · query: supplier performance, incidents, decisions, outcomes", med["id"],
                      meta={"count": len(memories), "total": recalled["total_results"],
                            "duration_ms": recalled["duration_ms"], "refs": [m["id"] for m in memories]})
        except Exception as exc:  # noqa: BLE001 - agent proceeds, clearly marked as memory-less
            s["status"] = "error"
            s["summary"] = f"Hindsight unavailable: {hs._describe(exc)}"
            log_event("error", "Hindsight recall failed — deciding without operational memory",
                      hs._describe(exc), med["id"])

    evidence = delivery_evidence(memories, med["id"])
    _summarise_experiences(memories)
    context = {"facts": facts, "suppliers": suppliers}

    engine = f"llm:{llm.settings.groq_model}"
    with trace.step("create_replenishment_recommendation", "Generate recommendation (with memory vs. without)") as s:
        with_mem, without_mem = await asyncio.gather(
            llm.complete_json(SYSTEM_PROMPT, build_user_prompt(context, memories)),
            llm.complete_json(SYSTEM_PROMPT, build_user_prompt(context, None), max_tokens=1000),
            return_exceptions=True,
        )
        if isinstance(with_mem, Exception):
            engine = "rules"
            llm_error = str(with_mem)[:120]
            with_mem = _rules_recommendation(facts, suppliers, memories, evidence, use_memory=True)
            s["summary"] = f"LLM unavailable ({llm_error}); deterministic decision engine used"
        else:
            s["summary"] = f"{llm.settings.groq_model} produced structured recommendations (with and without memory)"
        if isinstance(without_mem, Exception):
            without_mem = _rules_recommendation(facts, suppliers, [], [], use_memory=False)

    with trace.step("validate_recommendation", "Validate recommendation") as s:
        rec = _validate(with_mem, med, facts, suppliers, memories, evidence)
        base = _validate(without_mem, med, facts, suppliers, [], [])
        s["summary"] = (f"With memory → {rec['supplier_name']}, {rec['quantity']} units; "
                        f"without memory → {base['supplier_name']}"
                        + (f" · {'; '.join(rec['validation_notes'])}" if rec["validation_notes"] else ""))

    decision_id = _next_id("decisions", "DEC", 3001)
    # A newer analysis supersedes an older pending one for the same medicine.
    db.execute("UPDATE decisions SET status = 'superseded' WHERE medicine_id = ? AND status = 'pending'", (med["id"],))
    with trace.step("store_decision", "Store decision and request manager approval") as s:
        db.insert("decisions", {
            "id": decision_id, "medicine_id": med["id"], "created_at": _now(), "status": "pending", "source": "agent",
            "risk_level": med["risk_level"], "days_remaining": med["days_remaining"],
            "current_stock": med["current_stock"], "daily_demand": med["daily_demand"],
            "recommended_supplier_id": rec["supplier_id"], "recommended_quantity": rec["quantity"],
            "planning_lead_days": rec["lead_days"], "final_supplier_id": None, "final_quantity": None,
            "urgency": rec["urgency"], "confidence": rec["confidence"], "headline": rec["headline"],
            "assessment": rec["assessment"], "reason": rec["reason"], "why": rec["why"],
            "memory_used": rec["memory_used"], "memories_recalled": memories, "alternatives": rec["alternatives"],
            "baseline": {"supplier_id": base["supplier_id"], "supplier_name": base["supplier_name"],
                         "quantity": base["quantity"], "lead_days": base["lead_days"], "headline": base["headline"],
                         "reason": base["reason"], "arrives_before_stockout": base["arrives_before_stockout"]},
            "memory_state": memory_state, "recall_query": recall_query, "engine": engine, "trace": [],
            "order_id": None, "manager_note": None, "approved_at": None, "rejected_at": None, "outcome": None,
            "outcome_at": None, "retained_document_id": None,
        })
        s["summary"] = f"{decision_id} awaiting manager approval"
    db.update("decisions", "id", decision_id, {"trace": trace.steps})
    _ensure_open_incident(med, decision_id)
    log_event("recommend", f"Recommendation generated — {rec['supplier_name']} replenishment",
              f"{med['name']} · {rec['quantity']} units · {len(rec['memory_used'])} memories cited", med["id"],
              decision_id, {"supplier_id": rec["supplier_id"], "baseline_supplier_id": base["supplier_id"],
                            "engine": engine})
    return get_decision(decision_id)


def _ensure_open_incident(med: dict[str, Any], decision_id: str) -> None:
    if med["risk_level"] not in ("CRITICAL", "HIGH"):
        return
    existing = db.query_one(
        "SELECT id FROM incidents WHERE medicine_id = ? AND status IN ('open','monitoring') AND type = 'stock_out_risk'",
        (med["id"],))
    if existing:
        db.update("incidents", "id", existing["id"], {"decision_id": decision_id, "action": "Agent recommendation pending approval"})
        return
    db.insert("incidents", {
        "id": _next_id("incidents", "INC", 1013), "medicine_id": med["id"], "type": "stock_out_risk",
        "title": f"{med['generic_name']} stock-out risk", "severity": med["risk_level"].lower(),
        "occurred_at": _now(), "cause": f"Cover fell to {_fmt_days(med['days_remaining'])} days "
                                        f"({med['current_stock']} units at {_fmt_days(med['daily_demand'])}/day)",
        "action": "Agent recommendation pending approval", "supplier_id": None, "outcome": "Pending",
        "status": "open", "decision_id": decision_id, "memory_document_id": None, "memory_status": "not_retained",
    })


# ── manager decisions ────────────────────────────────────────────────────────

def _require(decision_id: str, statuses: tuple[str, ...]) -> dict[str, Any]:
    d = db.query_one("SELECT * FROM decisions WHERE id = ?", (decision_id,))
    if not d:
        raise AgentError(f"Decision {decision_id} not found")
    if d["status"] not in statuses:
        raise AgentError(f"Decision {decision_id} is {d['status']}; expected {' or '.join(statuses)}")
    return d


def record_manager_decision(decision_id: str, supplier_id: str | None, quantity: int | None,
                            note: str | None) -> dict[str, Any]:
    d = _require(decision_id, ("pending",))
    med = get_medicine_details(d["medicine_id"])
    supplier_id = supplier_id or d["recommended_supplier_id"]
    if supplier_id not in med["approved_supplier_ids"]:
        raise AgentError(f"{supplier_id} is not an approved supplier for {med['name']}")
    quantity = int(quantity or d["recommended_quantity"])
    if quantity <= 0 or quantity > 100000:
        raise AgentError("Quantity must be a positive number of units")
    supplier = db.query_one("SELECT * FROM suppliers WHERE id = ?", (supplier_id,))
    modified = supplier_id != d["recommended_supplier_id"] or quantity != d["recommended_quantity"]
    order_id = _next_id("orders", "PO", 4200)
    db.insert("orders", {
        "id": order_id, "medicine_id": med["id"], "supplier_id": supplier_id, "quantity": quantity,
        "ordered_at": _now(), "expected_days": supplier["contracted_lead_days"], "actual_days": None,
        "delivered_qty": None, "status": "in_transit", "urgency": d["urgency"], "decision_id": decision_id,
    })
    db.update("decisions", "id", decision_id, {
        "status": "approved", "final_supplier_id": supplier_id, "final_quantity": quantity,
        "manager_note": note or None, "approved_at": _now(), "order_id": order_id,
    })
    db.execute("UPDATE incidents SET action = ?, supplier_id = ? WHERE decision_id = ? AND status != 'resolved'",
               (f"{d['urgency'].title()} order of {quantity} units from {supplier['name']} ({order_id})",
                supplier_id, decision_id))
    log_event("modify" if modified else "approve",
              f"Manager {'modified and approved' if modified else 'approved'} recommendation",
              f"{med['name']} · {quantity} units from {supplier['name']} · {order_id}", med["id"], decision_id,
              {"modified": modified, "order_id": order_id})
    return get_decision(decision_id)


async def reject_decision(decision_id: str, reason: str | None) -> dict[str, Any]:
    d = _require(decision_id, ("pending",))
    med = get_medicine_details(d["medicine_id"])
    supplier = db.query_one("SELECT name FROM suppliers WHERE id = ?", (d["recommended_supplier_id"],))
    db.update("decisions", "id", decision_id, {"status": "rejected", "rejected_at": _now(), "manager_note": reason})
    log_event("reject", "Manager rejected recommendation", f"{med['name']} · {reason or 'no reason given'}",
              med["id"], decision_id)
    if reason and reason.strip():
        content = (
            f"Manager feedback ({date.today():%d %b %Y}): the manager rejected the agent's recommendation to order "
            f"{d['recommended_quantity']} units of {med['name']} from {supplier['name']} "
            f"(\"{d['headline']}\"). Reason given by the manager: {reason.strip()}. Situation at the time: "
            f"{d['current_stock']} units on hand, {_fmt_days(d['daily_demand'])} units/day, "
            f"{_fmt_days(d['days_remaining'])} days of cover."
        )
        try:
            info = await retain_experience(
                document_id=f"feedback-{decision_id.lower()}", content=content, context="Manager feedback on a recommendation",
                category="manager_feedback", origin="agent", medicine_id=med["id"],
                supplier_id=d["recommended_supplier_id"], decision_id=decision_id,
                metadata={"outcome": "rejected", "occurred_on": _now(), "decision_id": decision_id})
            db.update("decisions", "id", decision_id, {"retained_document_id": info["document_id"]})
        except Exception:  # noqa: BLE001 - logged by retain_experience; the rejection itself stands
            pass
    return get_decision(decision_id)


# ── outcomes ─────────────────────────────────────────────────────────────────

def _classify(delivery_days: float, contract: float, stockout: bool) -> str:
    if stockout:
        return "failed"
    if delivery_days > contract + 0.5:
        return "delayed"
    return "successful"


def compose_outcome_memory(d: dict[str, Any], med: dict[str, Any], supplier: dict[str, Any],
                           primary: dict[str, Any], outcome: dict[str, Any]) -> str:
    today = date.today().strftime("%d %b %Y")
    rec_supplier = db.query_one("SELECT name FROM suppliers WHERE id = ?", (d["recommended_supplier_id"],))["name"]
    parts = [
        f"{med['name']} replenishment outcome ({today}). Stock was {d['current_stock']} units against average demand of "
        f"{_fmt_days(d['daily_demand'])} units/day (about {_fmt_days(d['days_remaining'])} days of cover, "
        f"{d['risk_level'].lower()} stock-out risk).",
    ]
    if d["final_supplier_id"] == d["recommended_supplier_id"] and d["final_quantity"] == d["recommended_quantity"]:
        parts.append(f"The inventory agent recommended ordering {d['final_quantity']} units from {supplier['name']} and "
                     f"the manager approved it.")
    else:
        parts.append(f"The inventory agent recommended {d['recommended_quantity']} units from {rec_supplier}; the manager "
                     f"changed the order to {d['final_quantity']} units from {supplier['name']}"
                     + (f" because: {d['manager_note']}." if d.get("manager_note") else "."))
    if d.get("reason"):
        parts.append(f"Decision rationale: {d['reason']}")
    parts.append(
        f"{supplier['name']} delivered {outcome['delivered_quantity']} units of {med['name']} in "
        f"{_fmt_days(outcome['delivery_days'])} days against a contracted {_fmt_days(supplier['contracted_lead_days'])} days.")
    parts.append("A stock-out occurred before the delivery arrived." if outcome["stockout_occurred"]
                 else "Stock-out avoided.")
    parts.append(f"Outcome: {outcome['result']}.")
    if outcome["result"] == "successful":
        lesson = f"Lesson: {supplier['name']} reliably delivered {med['generic_name']} under {d['urgency']} conditions"
        if supplier["id"] != primary["id"]:
            lesson += f"; it remains the preferred option over {primary['name']} when {med['generic_name']} cover is low"
        parts.append(lesson + ".")
    elif outcome["result"] == "delayed":
        parts.append(f"Lesson: plan with {_fmt_days(outcome['delivery_days'])} days, not the contracted "
                     f"{_fmt_days(supplier['contracted_lead_days'])} days, for urgent {med['generic_name']} orders from "
                     f"{supplier['name']}.")
    else:
        parts.append(f"Lesson: {supplier['name']} could not protect {med['generic_name']} availability at this level of "
                     f"cover; reorder earlier or use a faster supplier.")
    if outcome.get("notes"):
        parts.append(f"Manager notes: {outcome['notes']}")
    return " ".join(parts)


async def record_outcome(decision_id: str, delivered_quantity: int, delivery_days: float, stockout_occurred: bool,
                         notes: str | None) -> dict[str, Any]:
    d = _require(decision_id, ("approved",))
    med = get_medicine_details(d["medicine_id"])
    supplier = db.query_one("SELECT * FROM suppliers WHERE id = ?", (d["final_supplier_id"],))
    if delivered_quantity < 0 or delivery_days <= 0 or delivery_days > 60:
        raise AgentError("Delivered quantity must be ≥ 0 and delivery time between 0 and 60 days")
    result = _classify(delivery_days, supplier["contracted_lead_days"], stockout_occurred)
    outcome = {
        "result": result, "delivered_quantity": delivered_quantity, "delivery_days": delivery_days,
        "stockout_occurred": stockout_occurred, "stockout": "occurred" if stockout_occurred else "avoided",
        "expected_days": supplier["contracted_lead_days"], "notes": notes or None,
        "summary": (f"{supplier['name']} delivered {delivered_quantity} units in {_fmt_days(delivery_days)} days; "
                    f"stock-out {'occurred' if stockout_occurred else 'avoided'}."),
    }
    # Operational updates (system of record).
    if d.get("order_id"):
        db.update("orders", "id", d["order_id"], {
            "actual_days": delivery_days, "delivered_qty": delivered_quantity,
            "status": "delivered_late" if delivery_days > supplier["contracted_lead_days"] + 0.5 else "delivered"})
    consumed = round(med["daily_demand"] * delivery_days)
    new_stock = max(med["current_stock"] - consumed, 0) + delivered_quantity
    db.update("medicines", "id", med["id"], {"current_stock": new_stock})
    today = date.today().isoformat()
    db.execute("""INSERT INTO stock_history (medicine_id, day, closing_stock, dispensed, received) VALUES (?,?,?,?,?)
                  ON CONFLICT(medicine_id, day) DO UPDATE SET closing_stock = excluded.closing_stock,
                  received = stock_history.received + excluded.received""",
               (med["id"], today, new_stock, 0, delivered_quantity))
    db.update("decisions", "id", decision_id, {"status": "completed", "outcome": outcome, "outcome_at": _now()})
    incident_outcome = ("Stock-out avoided" if not stockout_occurred else "Stock-out occurred") + \
                       f" — {supplier['name']} delivered in {_fmt_days(delivery_days)} days"
    db.execute("UPDATE incidents SET status = 'resolved', outcome = ?, memory_status = 'pending' WHERE decision_id = ?",
               (incident_outcome, decision_id))
    log_event("outcome", f"Outcome recorded — {result}", f"{med['name']} · {outcome['summary']}", med["id"],
              decision_id, {"result": result})

    # The outcome is saved either way; a failed retain is reported and can be retried from the decision.
    retain_error = None
    try:
        await retain_outcome(decision_id)
    except AgentError as exc:
        retain_error = str(exc)
    return {**get_decision(decision_id), "retain_error": retain_error}


async def retain_outcome(decision_id: str) -> dict[str, Any]:
    """Retain the completed decision's experience in Hindsight (also used for retries)."""
    d = _require(decision_id, ("completed",))
    med = get_medicine_details(d["medicine_id"])
    supplier = db.query_one("SELECT * FROM suppliers WHERE id = ?", (d["final_supplier_id"],))
    primary = db.query_one("SELECT * FROM suppliers WHERE id = ?", (med["primary_supplier_id"],))
    outcome = d["outcome"]
    content = compose_outcome_memory(d, med, supplier, primary, outcome)
    category = {"successful": "successful_outcome", "delayed": "supplier_knowledge"}.get(outcome["result"],
                                                                                         "stock_out_incident")
    document_id = f"outcome-{decision_id.lower()}"
    try:
        info = await retain_experience(
            document_id=document_id, content=content, context="Replenishment decision and outcome",
            category=category, origin="agent", medicine_id=med["id"], supplier_id=supplier["id"],
            decision_id=decision_id,
            metadata={"supplier_id": supplier["id"], "expected_delivery_days": _fmt_days(supplier["contracted_lead_days"]),
                      "actual_delivery_days": _fmt_days(outcome["delivery_days"]), "outcome": outcome["result"],
                      "quantity": outcome["delivered_quantity"], "occurred_on": _now(),
                      "decision_id": decision_id})
    except Exception as exc:  # noqa: BLE001
        db.execute("UPDATE incidents SET memory_status = 'failed' WHERE decision_id = ?", (decision_id,))
        db.update("decisions", "id", decision_id, {"retained_document_id": None})
        raise AgentError(f"Hindsight retain failed: {hs._describe(exc)}") from exc
    db.update("decisions", "id", decision_id, {"retained_document_id": document_id})
    db.execute("UPDATE incidents SET memory_status = 'retained', memory_document_id = ? WHERE decision_id = ?",
               (document_id, decision_id))
    return {**info, "content": content}


# ── read model ───────────────────────────────────────────────────────────────

def _timeline(d: dict[str, Any]) -> list[dict[str, Any]]:
    trace = {s["tool"]: s for s in d.get("trace") or []}
    recall = trace.get("recall_hindsight_memory")
    steps = [
        {"key": "detected", "label": "Detected", "done": True, "at": d["created_at"]},
        {"key": "analyzed", "label": "Analyzed", "done": True, "at": d["created_at"]},
        {"key": "recalled", "label": "Memory recalled", "done": d["source"] != "agent" or bool(recall and recall["status"] == "ok"),
         "at": d["created_at"], "detail": recall["summary"] if recall else None},
        {"key": "recommended", "label": "Recommendation created", "done": True, "at": d["created_at"]},
    ]
    if d["status"] == "rejected":
        steps.append({"key": "rejected", "label": "Rejected", "done": True, "at": d["rejected_at"]})
        return steps
    steps.append({"key": "approved", "label": "Approved", "done": d["approved_at"] is not None, "at": d["approved_at"]})
    steps.append({"key": "outcome", "label": "Outcome recorded" if d["outcome"] else "Awaiting outcome",
                  "done": d["outcome"] is not None, "at": d["outcome_at"]})
    steps.append({"key": "retained", "label": "Experience retained", "done": d["retained_document_id"] is not None,
                  "at": d["outcome_at"]})
    return steps


def get_decision(decision_id: str) -> dict[str, Any]:
    d = db.query_one(
        """SELECT d.*, m.name AS medicine_name, m.generic_name, m.category, m.pack_size,
                  s.name AS recommended_supplier_name, fs.name AS final_supplier_name,
                  ps.name AS primary_supplier_name, m.primary_supplier_id
           FROM decisions d JOIN medicines m ON m.id = d.medicine_id
           JOIN suppliers s ON s.id = d.recommended_supplier_id
           JOIN suppliers ps ON ps.id = m.primary_supplier_id
           LEFT JOIN suppliers fs ON fs.id = d.final_supplier_id WHERE d.id = ?""", (decision_id,))
    if not d:
        raise AgentError(f"Decision {decision_id} not found")
    d["timeline"] = _timeline(d)
    return d


def list_decisions(status: str | None = None, medicine_id: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT id FROM decisions WHERE 1=1"
    params: list[Any] = []
    if status:
        sql += f" AND status IN ({','.join('?' for _ in status.split(','))})"
        params.extend(status.split(","))
    if medicine_id:
        sql += " AND medicine_id = ?"
        params.append(medicine_id)
    sql += " ORDER BY created_at DESC"
    return [get_decision(r["id"]) for r in db.query(sql, tuple(params))]
