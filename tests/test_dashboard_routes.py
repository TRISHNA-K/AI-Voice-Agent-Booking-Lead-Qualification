"""Unit and integration tests for Web Dashboard API routes."""

import pytest
from starlette.testclient import TestClient
from src.server.app import create_app


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_dashboard_ui_html(client):
    """Verify that root endpoint serves the Web Dashboard HTML page."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "NovaTech Voice AI" in resp.text
    assert "Live Interactive Agent Simulator" in resp.text


def test_dashboard_metrics(client):
    """Verify metrics calculation endpoint."""
    resp = client.get("/api/dashboard/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "kpis" in data
    assert "stage_funnel" in data
    assert "total_calls" in data["kpis"]
    assert "appointments_booked" in data["kpis"]


def test_dashboard_crm_leads(client):
    """Verify CRM leads listing endpoint."""
    resp = client.get("/api/dashboard/crm/leads")
    assert resp.status_code == 200
    data = resp.json()
    assert "leads" in data
    assert isinstance(data["leads"], list)


def test_dashboard_appointments(client):
    """Verify appointment management and dynamic slots endpoint."""
    resp = client.get("/api/dashboard/appointments")
    assert resp.status_code == 200
    data = resp.json()
    assert "bookings" in data
    assert "upcoming_slots" in data
    assert len(data["upcoming_slots"]) > 0


def test_dashboard_calls(client):
    """Verify call history listing endpoint."""
    resp = client.get("/api/dashboard/calls")
    assert resp.status_code == 200
    data = resp.json()
    assert "calls" in data
    assert isinstance(data["calls"], list)


def test_dashboard_settings(client):
    """Verify settings endpoint returns configuration without exposing raw secrets."""
    resp = client.get("/api/dashboard/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "app_name" in data
    assert "mode" in data
    assert "integrations" in data
    assert "cal_com" in data["integrations"]


def test_dashboard_agent_chat_alex(client):
    """Verify interactive conversation endpoint with Alex (Inbound)."""
    resp = client.get("/api/dashboard/metrics")  # warm up
    chat_resp = client.post(
        "/api/dashboard/agent/chat",
        json={
            "session_id": "test_session_1",
            "agent_id": "alex",
            "message": "Hello, I want to schedule an appointment for tomorrow.",
        },
    )
    assert chat_resp.status_code == 200
    data = chat_resp.json()
    assert "speech" in data
    assert len(data["speech"]) > 0
    assert "tool_calls" in data


def test_dashboard_agent_chat_jordan(client):
    """Verify interactive conversation endpoint with Jordan (Outbound)."""
    chat_resp = client.post(
        "/api/dashboard/agent/chat",
        json={
            "session_id": "test_session_2",
            "agent_id": "jordan",
            "message": "Yes, I have two minutes. We lose leads due to missed phone calls.",
        },
    )
    assert chat_resp.status_code == 200
    data = chat_resp.json()
    assert "speech" in data
    assert len(data["speech"]) > 0
