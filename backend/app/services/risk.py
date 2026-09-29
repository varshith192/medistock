"""Deterministic risk engine. All arithmetic happens here, never in the LLM."""
from __future__ import annotations

from datetime import date
from typing import Any

from app.database import db

RISK_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def exact_days_remaining(stock: float, daily_demand: float) -> float:
    """days_remaining = current_stock / average_daily_demand (unrounded; used for risk tiers)."""
    if daily_demand <= 0:
        return 999.0
    return stock / daily_demand


def days_remaining(stock: float, daily_demand: float) -> float:
    return round(exact_days_remaining(stock, daily_demand), 1)


def risk_level(days: float) -> str:
    if days <= 2:
        return "CRITICAL"
    if days <= 4:
        return "HIGH"
    if days <= 7:
        return "MEDIUM"
    return "LOW"


def expiry_threshold_days() -> int:
    return int(db.get_setting("expiry_threshold_days", "60"))


def target_cover_days() -> float:
    return float(db.get_setting("target_cover_days", "7"))


def round_up(value: float, step: int) -> int:
    step = max(int(step), 1)
    return max(step, int(-(-value // step)) * step)


def recommended_quantity(stock: int, demand: float, lead_days: float, pack: int, moq: int) -> int:
    """Cover demand during the lead time plus the target cover window, rounded to packs and MOQ."""
    # Units consumed until the delivery lands plus the target cover window, less what is on hand.
    need = max(demand * (lead_days + target_cover_days()) - stock, 1)
    qty = round_up(need, max(pack, 1))
    return max(qty, round_up(moq, max(pack, 1)))


def supplier_performance() -> dict[str, dict[str, Any]]:
    """Delivery performance per supplier computed from delivered order records."""
    rows = db.query(
        """SELECT supplier_id, COUNT(*) AS orders, AVG(actual_days) AS avg_days, AVG(expected_days) AS exp_days,
                  SUM(CASE WHEN actual_days <= expected_days + 0.5 THEN 1 ELSE 0 END) AS on_time
           FROM orders WHERE actual_days IS NOT NULL GROUP BY supplier_id""")
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        on_time_pct = round(100 * r["on_time"] / r["orders"]) if r["orders"] else 0
        out[r["supplier_id"]] = {
            "orders": r["orders"],
            "avg_delivery_days": round(r["avg_days"], 1),
            "expected_delivery_days": round(r["exp_days"], 1),
            "on_time_pct": on_time_pct,
            "delay_rate": 100 - on_time_pct,
        }
    return out


def reliability_label(on_time_pct: float) -> str:
    if on_time_pct >= 88:
        return "Reliable"
    if on_time_pct >= 75:
        return "Watch"
    return "Needs Attention"


def supplier_is_risky(perf: dict[str, Any]) -> bool:
    return perf["avg_delivery_days"] > perf["expected_delivery_days"] * 1.25 or perf["on_time_pct"] < 75


def demand_trend(medicine_id: str) -> dict[str, float]:
    rows = db.query(
        "SELECT dispensed FROM stock_history WHERE medicine_id = ? ORDER BY day DESC LIMIT 28", (medicine_id,))
    values = [r["dispensed"] for r in rows]
    recent = values[:7]
    prior = values[7:28]
    recent_avg = sum(recent) / len(recent) if recent else 0.0
    prior_avg = sum(prior) / len(prior) if prior else recent_avg
    change = ((recent_avg - prior_avg) / prior_avg * 100) if prior_avg else 0.0
    return {"recent_avg": round(recent_avg, 1), "prior_avg": round(prior_avg, 1), "change_pct": round(change)}


def assess_medicine(med: dict[str, Any], perf: dict[str, dict[str, Any]] | None = None,
                    active_decision: dict[str, Any] | None = None) -> dict[str, Any]:
    """Enrich a medicine row with deterministic risk facts."""
    perf = perf if perf is not None else supplier_performance()
    dr = days_remaining(med["current_stock"], med["daily_demand"])
    level = risk_level(exact_days_remaining(med["current_stock"], med["daily_demand"]))
    days_to_expiry = (date.fromisoformat(med["expiry_date"]) - date.today()).days
    units_at_expiry_risk = max(0, round(med["current_stock"] - med["daily_demand"] * days_to_expiry))
    expiry_risk = days_to_expiry <= expiry_threshold_days()
    primary_perf = perf.get(med["primary_supplier_id"])
    supplier_risk = bool(primary_perf and supplier_is_risky(primary_perf))

    if active_decision and active_decision["status"] == "pending":
        agent_status = "Decision Pending"
    elif active_decision and active_decision["status"] == "approved":
        agent_status = "Awaiting Delivery"
    elif level in ("CRITICAL", "HIGH"):
        agent_status = "Action Required"
    elif level == "MEDIUM" or expiry_risk:
        agent_status = "Monitor"
    else:
        agent_status = "Healthy"

    return {
        **med,
        "days_remaining": dr,
        "risk_level": level,
        "days_to_expiry": days_to_expiry,
        "expiry_risk": expiry_risk,
        "units_at_expiry_risk": units_at_expiry_risk,
        "supplier_risk": supplier_risk,
        "agent_status": agent_status,
        "active_decision_id": active_decision["id"] if active_decision else None,
    }
