"""End-to-end test of the memory loop through the real SDK integration code:

retain (history) → recall → agent decision changes → approve → outcome → retain → recall both → decision.
"""
from __future__ import annotations

import asyncio

import pytest

from app.agents import inventory_agent as agent
from app.database import db
from app.seed.seed_db import seed_database
from app.services import demo, inventory, memory_service


@pytest.fixture(autouse=True)
def fresh_state(fake_hindsight_server):
    fake_hindsight_server.reset()
    seed_database(force=True)
    db.execute("DELETE FROM memory_registry")
    asyncio.run(memory_service.seed_memory())
    assert memory_service.seed_state["state"] == "done", memory_service.seed_state
    yield


def test_seed_history_is_retained_in_hindsight(fake_hindsight_server):
    docs = fake_hindsight_server.DOCS
    assert "seed-amox-supplier-a-delay" in docs
    a_delay = docs["seed-amox-supplier-a-delay"]
    assert a_delay["document_metadata"]["actual_delivery_days"] == "4"
    assert "medicine:MED-001" in a_delay["tags"] and "supplier:SUP-A" in a_delay["tags"]
    # Incidents linked to retained experiences are marked as retained.
    inc = db.query_one("SELECT memory_status FROM incidents WHERE id = 'INC-1001'")
    assert inc["memory_status"] == "retained"


def test_current_data_matches_demo_scenario():
    med = inventory.get_medicine("MED-001")
    assert (med["current_stock"], med["daily_demand"], med["days_remaining"], med["risk_level"]) == (42, 15, 2.8, "HIGH")


def test_full_memory_loop(fake_hindsight_server):
    # 1–6: analysis recalls the Supplier A delay and memory changes the recommendation.
    first = asyncio.run(agent.analyze("MED-001"))
    assert first["memory_state"] == "found"
    recalled_docs = {m["document_id"] for m in first["memories_recalled"]}
    assert {"seed-amox-supplier-a-delay", "seed-amox-supplier-b-success"} <= recalled_docs
    assert first["baseline"]["supplier_id"] == "SUP-A"          # without memory: contract says 2 days, looks safe
    assert first["recommended_supplier_id"] == "SUP-B"          # with memory: A really took 4 days > 2.8 days cover
    assert first["planning_lead_days"] == 1.5
    assert first["recommended_quantity"] == 100
    cited = {m["document_id"] for m in first["memory_used"]}
    assert "seed-amox-supplier-a-delay" in cited

    # 7: approve.
    approved = agent.record_manager_decision(first["id"], None, None, None)
    assert approved["status"] == "approved" and approved["order_id"]

    # 8–9: outcome recorded and retained.
    done = asyncio.run(agent.record_outcome(first["id"], 100, 1.5, False, None))
    assert done["status"] == "completed" and done["outcome"]["result"] == "successful"
    assert done["retain_error"] is None
    new_doc = done["retained_document_id"]
    assert new_doc == f"outcome-{first['id'].lower()}" and new_doc in fake_hindsight_server.DOCS
    stored = fake_hindsight_server.DOCS[new_doc]
    assert "Supplier B delivered 100 units" in stored["original_text"] and "Outcome: successful" in stored["original_text"]
    assert stored["document_metadata"]["actual_delivery_days"] == "1.5"

    # 10: a new similar situation recalls BOTH experiences and uses them.
    demo.new_situation("MED-001")
    second = asyncio.run(agent.analyze("MED-001"))
    recalled_docs = {m["document_id"] for m in second["memories_recalled"]}
    assert {"seed-amox-supplier-a-delay", new_doc} <= recalled_docs
    assert second["recommended_supplier_id"] == "SUP-B"
    cited = {m["document_id"] for m in second["memory_used"]}
    assert new_doc in cited and "seed-amox-supplier-a-delay" in cited


def test_newest_experience_is_recalled_among_many(fake_hindsight_server):
    """After repeated cycles, the latest outcome must still surface and be cited, not be crowded out."""
    latest = None
    for _ in range(3):
        d = asyncio.run(agent.analyze("MED-001"))
        agent.record_manager_decision(d["id"], None, None, None)
        latest = asyncio.run(agent.record_outcome(d["id"], 100, 1.5, False, None))["retained_document_id"]
        demo.new_situation("MED-001")
    final = asyncio.run(agent.analyze("MED-001"))
    assert latest in {m["document_id"] for m in final["memories_recalled"]}
    assert latest in {m["document_id"] for m in final["memory_used"]}


def test_rejection_retains_manager_feedback(fake_hindsight_server):
    d = asyncio.run(agent.analyze("MED-005"))
    rejected = asyncio.run(agent.reject_decision(d["id"], "Supplier E is on credit hold this month"))
    assert rejected["status"] == "rejected"
    doc = fake_hindsight_server.DOCS[f"feedback-{d['id'].lower()}"]
    assert "credit hold" in doc["original_text"] and "category:manager_feedback" in doc["tags"]


def test_validation_overrides_unsafe_supplier():
    med = agent.get_medicine_details("MED-001")
    facts = agent.calculate_stock_risk(med)
    suppliers = agent.get_supplier_terms(med)
    evidence = [{"ref": "M1", "document_id": "d1", "supplier_id": "SUP-A", "actual_delivery_days": 4.0,
                 "expected_delivery_days": 2.0, "outcome": "delayed", "occurred_on": "2026-09-12"},
                {"ref": "M2", "document_id": "d2", "supplier_id": "SUP-B", "actual_delivery_days": 1.5,
                 "expected_delivery_days": 2.0, "outcome": "successful", "occurred_on": "2026-09-18"}]
    proposal = {"recommended_supplier_id": "SUP-A", "headline": "Reorder from Supplier A", "why": [], "memory_used": []}
    checked = agent._validate(proposal, med, facts, suppliers, [], evidence)
    assert checked["supplier_id"] == "SUP-B" and checked["validation_notes"]


def test_analysis_blocked_while_order_in_transit():
    d = asyncio.run(agent.analyze("MED-001"))
    agent.record_manager_decision(d["id"], None, None, None)
    with pytest.raises(agent.AgentError, match="already in transit"):
        asyncio.run(agent.analyze("MED-001"))


def test_memory_overview_reads_from_hindsight():
    overview = asyncio.run(memory_service.memory_overview())
    assert overview["totals"]["documents"] == 9
    card = next(c for c in overview["documents"] if c["document_id"] == "seed-amox-supplier-a-delay")
    assert card["medicine_name"] == "Amoxicillin 500mg" and card["supplier_name"] == "Supplier A" and card["facts"]


def test_reset_removes_demo_memories(fake_hindsight_server):
    d = asyncio.run(agent.analyze("MED-001"))
    agent.record_manager_decision(d["id"], None, None, None)
    asyncio.run(agent.record_outcome(d["id"], 100, 1.5, False, None))
    assert f"outcome-{d['id'].lower()}" in fake_hindsight_server.DOCS

    async def reset_and_wait():
        result = await demo.reset_all()
        await asyncio.sleep(0)  # let the background bootstrap task start
        return result

    result = asyncio.run(reset_and_wait())
    assert result["removed_memories"] == 1
    assert not any(k.startswith("outcome-") for k in fake_hindsight_server.DOCS)
    assert "seed-amox-supplier-a-delay" in fake_hindsight_server.DOCS
