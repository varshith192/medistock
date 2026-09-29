"""API contract and failure-mode tests (validation, status codes, degraded dependencies)."""
from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
from hindsight_client import Hindsight

from app.hindsight import client as hs
from app.main import app
from app.seed.seed_db import seed_database
from app.services import risk


@pytest.fixture()
def api(fake_hindsight_server):
    fake_hindsight_server.reset()
    seed_database(force=True)
    # No context manager: the background bootstrap loop is not started in tests.
    return TestClient(app, raise_server_exceptions=False)


def test_read_endpoints(api):
    for path in ["/api/overview", "/api/inventory", "/api/inventory/MED-001", "/api/risks", "/api/suppliers",
                 "/api/incidents", "/api/decisions", "/api/events", "/api/settings", "/api/health"]:
        assert api.get(path).status_code == 200, path


def test_medicine_detail_decisions_render_as_cards(api):
    """The detail drawer renders the active decision with the same component as the Decision Center."""
    api.post("/api/agent/analyze", json={"medicine_id": "MED-001"})
    detail = api.get("/api/inventory/MED-001").json()
    active = [d for d in detail["decisions"] if d["status"] == "pending"]
    assert len(active) == 1
    assert active[0]["timeline"] and active[0]["medicine_name"] == "Amoxicillin 500mg"
    assert all(d["status"] != "superseded" for d in detail["decisions"])


def test_validation_and_status_codes(api):
    assert api.get("/api/inventory/MED-999").status_code == 404
    assert api.post("/api/agent/analyze", json={"medicine_id": "MED-999"}).status_code == 404
    assert api.post("/api/agent/analyze", json={}).status_code == 422
    assert api.post("/api/decisions/DEC-9999/approve", json={}).status_code == 404

    decision = api.post("/api/agent/analyze", json={"medicine_id": "MED-001"}).json()
    assert api.post(f"/api/decisions/{decision['id']}/approve", json={"quantity": 0}).status_code == 422
    assert api.post(f"/api/decisions/{decision['id']}/approve", json={"supplier_id": "SUP-F"}).status_code == 409
    assert api.post(f"/api/decisions/{decision['id']}/outcome",
                    json={"delivered_quantity": 100, "delivery_days": 1.5}).status_code == 409  # not approved yet
    assert api.post(f"/api/decisions/{decision['id']}/approve", json={}).status_code == 200
    assert api.post(f"/api/decisions/{decision['id']}/approve", json={}).status_code == 409  # duplicate approval
    assert api.post("/api/agent/analyze", json={"medicine_id": "MED-001"}).status_code == 409  # order in transit
    assert api.post(f"/api/decisions/{decision['id']}/outcome",
                    json={"delivered_quantity": -5, "delivery_days": 1.5}).status_code == 422
    ok = api.post(f"/api/decisions/{decision['id']}/outcome", json={"delivered_quantity": 100, "delivery_days": 1.5})
    assert ok.status_code == 200 and ok.json()["retained_document_id"]


def test_hindsight_unavailable_degrades_gracefully(api, monkeypatch):
    """Recall/retain failures never block the workflow and are reported, not hidden."""
    dead = {}

    def dead_client():
        loop = id(asyncio.get_running_loop())
        dead.setdefault(loop, Hindsight(base_url="http://127.0.0.1:1", api_key="x", timeout=2, max_attempts=1))
        return dead[loop]

    monkeypatch.setattr(hs, "get_client", dead_client)
    monkeypatch.setattr(hs, "_bank_ready", set())
    monkeypatch.setitem(hs.status, "checked_at", None)
    decision = api.post("/api/agent/analyze", json={"medicine_id": "MED-001"})
    assert decision.status_code == 200
    body = decision.json()
    assert body["memory_state"] == "unavailable" and body["memory_used"] == []
    assert api.post(f"/api/decisions/{body['id']}/approve", json={}).status_code == 200
    outcome = api.post(f"/api/decisions/{body['id']}/outcome", json={"delivered_quantity": 100, "delivery_days": 2})
    assert outcome.status_code == 200
    assert outcome.json()["status"] == "completed" and outcome.json()["retain_error"]
    health = api.get("/api/health").json()
    assert health["hindsight"]["connected"] is False and health["hindsight"]["error"]
    assert api.get("/api/memory").status_code == 502


def test_unexpected_errors_are_not_leaked(api, monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr("app.services.inventory.list_inventory", boom)
    response = api.get("/api/inventory")
    assert response.status_code == 500
    assert "secret" not in response.text and "Unexpected server error" in response.json()["detail"]


@pytest.mark.parametrize("stock,demand,level", [
    (30, 15, "CRITICAL"), (31, 15, "HIGH"), (60, 15, "HIGH"), (61, 15, "MEDIUM"), (105, 15, "MEDIUM"), (106, 15, "LOW"),
    (51, 25, "HIGH"),  # 2.04 days: rounds to 2.0 for display but is not critical
])
def test_risk_tiers(stock, demand, level):
    assert risk.risk_level(risk.exact_days_remaining(stock, demand)) == level


def test_recommended_quantity_is_deterministic():
    # 15/day, 1.5-day lead, 7-day target cover, 42 on hand → 85.5 → rounded up to pack of 50 → 100
    assert risk.recommended_quantity(42, 15, 1.5, 50, 50) == 100
