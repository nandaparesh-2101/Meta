from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/api_test.db")
    import app.api.routes as routes_module
    from app.memory.store import MemoryStore
    from app.orchestration.workflow import Orchestrator

    routes_module._memory = MemoryStore(db_path=tmp_path / "api_test.db")
    routes_module._orchestrator = Orchestrator(memory=routes_module._memory)

    from app.main import app

    return TestClient(app)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_status_reports_mock_mode_and_disabled_execution(client):
    response = client.get("/status")
    body = response.json()
    assert body["data_mode"] == "mock"
    assert body["execution_mode"] == "disabled"
    assert body["meta_api_connected"] is False


def test_analyze_returns_report_and_recommendations(client):
    response = client.post("/analyze", json={"trigger": "cpl_increase", "scenario": "high_cpl_campaign"})
    assert response.status_code == 200
    body = response.json()
    assert body["finding_count"] > 0
    assert "1. Business Objective" in body["report"]


def test_analyze_rejects_unknown_scenario(client):
    response = client.post("/analyze", json={"scenario": "not_a_real_scenario"})
    assert response.status_code == 400


def test_experiments_learnings_audit_endpoints_after_analyze(client):
    client.post("/analyze", json={"trigger": "ctr_decrease", "scenario": "creative_fatigue"})
    assert client.get("/experiments").status_code == 200
    assert client.get("/learnings").status_code == 200
    audit_response = client.get("/audit")
    assert audit_response.status_code == 200
    assert len(audit_response.json()) > 0


def test_execute_endpoint_always_reports_disabled(client):
    response = client.post("/execute")
    assert response.status_code == 200
    body = response.json()
    assert body["executed"] is False
    assert body["execution_mode"] == "disabled"
