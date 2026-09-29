"""Historical operational experiences retained into Hindsight on first start.

These are written as distilled operational knowledge (what happened, why, outcome, lesson),
not raw conversation logs. They are retained through the real Hindsight API.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone


def _d(days_ago: int) -> date:
    return date.today() - timedelta(days=days_ago)


def _fmt(d: date) -> str:
    return d.strftime("%d %b %Y").lstrip("0")


def seed_experiences() -> list[dict]:
    """Return the seed experiences with dates anchored to today."""
    amox_a_order, amox_a_delivered, amox_low = _d(16), _d(12), _d(13)
    amox_b_order, amox_b_delivered = _d(10), _d(9)

    items = [
        {
            "document_id": "seed-amox-supplier-a-delay",
            "incident_id": "INC-1001",
            "occurred": amox_a_order,
            "category": "stock_out_incident",
            "medicine_id": "MED-001",
            "supplier_id": "SUP-A",
            "context": "Stock-out incident and supplier delivery delay",
            "content": (
                f"Amoxicillin 500mg stock-out risk incident ({_fmt(amox_a_order)}). Amoxicillin stock had fallen to 55 units "
                f"against average demand of about 15 units/day (roughly 3.7 days of cover). The manager placed an emergency "
                f"reorder of 100 units with the primary supplier, Supplier A (Meridian Pharma Distributors), relying on its "
                f"contracted 2-day lead time. Supplier A actually took 4 days to deliver Amoxicillin (delivered {_fmt(amox_a_delivered)}) "
                f"because of an antibiotic allocation backlog at its warehouse. Amoxicillin stock fell to 8 units on "
                f"{_fmt(amox_low)} and dispensing had to be rationed. Outcome: delivery delayed, near stock-out. "
                f"Lesson: Supplier A's real lead time for urgent Amoxicillin orders has been about 4 days, double its "
                f"contracted 2 days; do not rely on Supplier A when Amoxicillin cover is below 4 days."
            ),
            "metadata": {"supplier_id": "SUP-A", "expected_delivery_days": "2", "actual_delivery_days": "4",
                         "outcome": "delayed", "quantity": "100"},
        },
        {
            "document_id": "seed-amox-supplier-b-success",
            "incident_id": "INC-1002",
            "occurred": amox_b_order,
            "category": "successful_outcome",
            "medicine_id": "MED-001",
            "supplier_id": "SUP-B",
            "context": "Replenishment decision and successful outcome",
            "content": (
                f"Amoxicillin 500mg urgent replenishment ({_fmt(amox_b_order)}). A seasonal respiratory-infection demand spike pushed "
                f"Amoxicillin demand to about 22 units/day and stock dropped to 54 units (about 2.5 days of cover). Because "
                f"Supplier A had taken 4 days on the previous Amoxicillin order, the manager placed an urgent order of 150 units "
                f"with Supplier B (Carewell Pharma Supply) instead. Supplier B delivered Amoxicillin in 1.5 days (contracted 2 days), "
                f"arriving {_fmt(amox_b_delivered)}. Stock never fell below 32 units. Outcome: successful, stock-out avoided. "
                f"Lesson: for urgent Amoxicillin replenishment, Supplier B is the proven fast option."
            ),
            "metadata": {"supplier_id": "SUP-B", "expected_delivery_days": "2", "actual_delivery_days": "1.5",
                         "outcome": "successful", "quantity": "150"},
        },
        {
            "document_id": "seed-supplier-a-routine-performance",
            "incident_id": None,
            "occurred": _d(35),
            "category": "supplier_knowledge",
            "medicine_id": None,
            "supplier_id": "SUP-A",
            "context": "Supplier performance review",
            "content": (
                f"Supplier performance review ({_fmt(_d(35))}): Supplier A (Meridian Pharma Distributors) delivered routine orders "
                f"for Metformin, Amlodipine and Atorvastatin on time, typically in 2 to 2.5 days. Supplier A's delays have been "
                f"concentrated on antibiotics (Amoxicillin, Ceftriaxone, Doxycycline) where its allocation from the manufacturer is "
                f"constrained; antibiotic orders from Supplier A have taken 3 to 4 days. Supplier A remains acceptable for routine "
                f"chronic-therapy medicines."
            ),
            "metadata": {"supplier_id": "SUP-A", "outcome": "mixed"},
        },
        {
            "document_id": "seed-supplier-b-reliability",
            "incident_id": None,
            "occurred": _d(20),
            "category": "supplier_knowledge",
            "medicine_id": None,
            "supplier_id": "SUP-B",
            "context": "Supplier performance review",
            "content": (
                f"Supplier performance review ({_fmt(_d(20))}): Supplier B (Carewell Pharma Supply) delivered all of its recent "
                f"orders within the contracted 2-day lead time, averaging 1.7 days, including urgent orders for Azithromycin "
                f"and Paracetamol. Supplier B has a minimum order quantity of 50 units per line and charges roughly 4% more per unit "
                f"than Supplier A on antibiotics."
            ),
            "metadata": {"supplier_id": "SUP-B", "actual_delivery_days": "1.7", "outcome": "reliable"},
        },
        {
            "document_id": "seed-manager-feedback-antibiotics",
            "incident_id": None,
            "occurred": _d(24),
            "category": "manager_feedback",
            "medicine_id": None,
            "supplier_id": None,
            "context": "Manager feedback on replenishment policy",
            "content": (
                f"Manager feedback ({_fmt(_d(24))}): for antibiotics, urgent replenishment orders should cover about 7 to 10 days of "
                f"demand, not more, to avoid expiry write-offs. When cover is critically low, stock-out prevention takes priority "
                f"over the small price premium of a faster supplier. Avoid splitting an order across suppliers below 50 units."
            ),
            "metadata": {"outcome": "policy"},
        },
        {
            "document_id": "seed-cefixime-expiry",
            "incident_id": "INC-1003",
            "occurred": _d(39),
            "category": "expiry_incident",
            "medicine_id": "MED-036",
            "supplier_id": "SUP-C",
            "context": "Expiry write-off incident",
            "content": (
                f"Cefixime 200mg expiry write-off ({_fmt(_d(39))}): 180 tablets expired after a bulk order of 400 units from "
                f"Supplier C was placed to get a volume discount while Cefixime demand was only about 6 units/day. The write-off "
                f"cost more than the discount saved. Lesson: cap Cefixime orders at about 30 days of demand and watch short-dated "
                f"Cefixime batches."
            ),
            "metadata": {"supplier_id": "SUP-C", "outcome": "write_off", "quantity": "400"},
        },
        {
            "document_id": "seed-insulin-coldchain-delay",
            "incident_id": "INC-1004",
            "occurred": _d(26),
            "category": "stock_out_incident",
            "medicine_id": "MED-005",
            "supplier_id": "SUP-D",
            "context": "Cold-chain supplier delay",
            "content": (
                f"Insulin Glargine cold-chain incident ({_fmt(_d(26))}): Supplier D (Nova Coldchain Logistics) delivered an order 3 days "
                f"late (5 days against a 2-day contract) and one carton failed the 2-8°C temperature check, so 20 pens were rejected. "
                f"Supplier E (Sterling Biologics) delivered a replacement order of Insulin Glargine in 1 day and prevented a stock-out. "
                f"Lesson: for urgent cold-chain insulin, prefer Supplier E; Supplier D is unreliable on urgent orders."
            ),
            "metadata": {"supplier_id": "SUP-D", "expected_delivery_days": "2", "actual_delivery_days": "5",
                         "outcome": "delayed"},
        },
        {
            "document_id": "seed-ors-demand-spike",
            "incident_id": "INC-1005",
            "occurred": _d(33),
            "category": "medicine_pattern",
            "medicine_id": "MED-006",
            "supplier_id": "SUP-C",
            "context": "Seasonal demand pattern",
            "content": (
                f"ORS sachet demand pattern ({_fmt(_d(33))}): during the late-monsoon period ORS demand roughly tripled, from about 14 to "
                f"about 40 sachets/day, for three to four weeks. A standing order with Supplier C kept stock available, but cover "
                f"dropped below 2 days twice. Lesson: raise ORS safety stock ahead of monsoon peaks; Supplier F is slower (4 days) and "
                f"not suitable for urgent ORS top-ups."
            ),
            "metadata": {"supplier_id": "SUP-C", "outcome": "stock_maintained"},
        },
        {
            "document_id": "seed-azithro-supplier-b",
            "incident_id": "INC-1006",
            "occurred": _d(23),
            "category": "replenishment_decision",
            "medicine_id": "MED-003",
            "supplier_id": "SUP-B",
            "context": "Replenishment decision and outcome",
            "content": (
                f"Azithromycin 500mg urgent replenishment ({_fmt(_d(23))}): with about 2 days of cover left, the manager ordered 60 units "
                f"from Supplier B. Supplier B delivered in 2 days as contracted. Outcome: successful, no stock-out."
            ),
            "metadata": {"supplier_id": "SUP-B", "expected_delivery_days": "2", "actual_delivery_days": "2",
                         "outcome": "successful", "quantity": "60"},
        },
    ]
    for item in items:
        occurred: date = item["occurred"]
        item["timestamp"] = datetime.combine(occurred, time(10, 0), tzinfo=timezone.utc)
        tags = [f"category:{item['category']}", "origin:seed"]
        if item["medicine_id"]:
            tags.append(f"medicine:{item['medicine_id']}")
        if item["supplier_id"]:
            tags.append(f"supplier:{item['supplier_id']}")
        item["tags"] = tags
        item["metadata"] = {**item["metadata"], "category": item["category"],
                            "medicine_id": item["medicine_id"] or "", "occurred_on": occurred.isoformat()}
    return items
