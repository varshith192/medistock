"""Recall selection on result shapes observed from Hindsight Cloud: world facts carry a document,
consolidated observations restate them without one, and policy memories repeat across both."""
from __future__ import annotations

from app.hindsight.recall import select_relevant

AMOX = {"id": "MED-001", "generic_name": "Amoxicillin"}


def mem(i, text, category, doc=None, medicine=None, supplier=None, fact_type="world"):
    return {"id": f"f{i}", "ref": f"M{i}", "text": text, "fact_type": fact_type, "document_id": doc,
            "category": category, "medicine_id": medicine, "supplier_id": supplier, "metadata": {}}


def test_policy_repeats_do_not_crowd_out_medicine_history():
    policy = [
        "Manager mandated that stock-out prevention takes priority over price premiums for faster suppliers",
        "Manager instructed to avoid splitting orders across multiple suppliers below 50 units",
        "Manager set a replenishment policy for antibiotics covering 7 to 10 days of demand",
    ]
    items = []
    for n, text in enumerate(policy):  # each policy as a fact and as a consolidated observation, ranked first
        items.append(mem(len(items), text, "manager_feedback", doc="policy-doc"))
        items.append(mem(len(items), "The " + text.lower(), "manager_feedback", fact_type="observation"))
    items += [
        mem(20, "Supplier A took 4 days to deliver Amoxicillin against a 2-day contract", "stock_out_incident",
            doc="amox-a-delay", medicine="MED-001", supplier="SUP-A"),
        mem(21, "Supplier B delivered urgent Amoxicillin in 1.5 days; stock-out avoided", "successful_outcome",
            doc="amox-b-success", medicine="MED-001", supplier="SUP-B"),
        mem(22, "Supplier B delivered 100 units of Amoxicillin in 1.5 days; outcome successful", "successful_outcome",
            doc="outcome-dec-3001", medicine="MED-001", supplier="SUP-B"),
        mem(23, "Insulin Glargine delivered late by Supplier D", "stock_out_incident", doc="insulin",
            medicine="MED-005", supplier="SUP-D"),
    ]
    selected = select_relevant(items, AMOX, ["SUP-A", "SUP-B", "SUP-C"])
    docs = [m["document_id"] for m in selected]
    assert {"amox-a-delay", "amox-b-success", "outcome-dec-3001"} <= set(docs)
    assert sum(1 for m in selected if m["category"] == "manager_feedback") <= 2
    assert "insulin" not in docs                              # other medicines' memories are excluded
    assert docs[:3] == ["amox-a-delay", "amox-b-success", "outcome-dec-3001"]  # medicine history first


def test_similar_outcomes_from_different_experiences_are_kept():
    template = "Amoxicillin replenishment outcome: Supplier B delivered 100 units in 1.5 days; stock-out avoided"
    items = [mem(1, template, "successful_outcome", doc="outcome-dec-3001", medicine="MED-001"),
             mem(2, template, "successful_outcome", doc="outcome-dec-3002", medicine="MED-001"),
             mem(3, template, "successful_outcome", fact_type="observation", medicine="MED-001")]
    docs = [m["document_id"] for m in select_relevant(items, AMOX, ["SUP-B"])]
    assert docs == ["outcome-dec-3001", "outcome-dec-3002"]   # the observation restating them is dropped
