"""Integration tests for FastAPI endpoints."""

import pytest


def test_health_endpoint(test_client):
    res = test_client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["integrations"]["dograh_ai"] == "ready"


def test_platform_status_endpoint(test_client):
    res = test_client.get("/api/v1/status")
    assert res.status_code == 200
    data = res.json()
    assert "app_name" in data


def test_check_slots_endpoint(test_client):
    payload = {"date_str": "tomorrow", "max_options": 2}
    res = test_client.post("/tools/calcom/check-slots", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["available"] is True
    assert len(data["slots"]) <= 2


def test_book_appointment_endpoint(test_client):
    payload = {
        "start_time": "tomorrow at 3pm",
        "name": "Clark Kent",
        "email": "clark@dailyplanet.example",
        "notes": "Discussion about Voice AI implementation",
        "phone_number": "+15554567890",
    }
    res = test_client.post("/tools/calcom/book-appointment", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "booking_id" in data


def test_cancel_appointment_endpoint(test_client):
    payload = {"booking_id": "cal_book_test_1", "reason": "Schedule conflict"}
    res = test_client.post("/tools/calcom/cancel-appointment", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True


def test_transfer_call_endpoint(test_client):
    payload = {"transfer_reason": "Customer requested human supervisor", "caller_name": "Diana Prince"}
    res = test_client.post("/tools/telephony/transfer-call", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "transfer_initiated"
    assert "speech" in data


def test_dograh_call_ended_webhook(test_client):
    payload = {
        "call_id": "dograh_call_999",
        "direction": "inbound",
        "duration_seconds": 95,
        "phone_number": "+15559871111",
        "transcript": "Caller: I want to book tomorrow. Agent: You are booked.",
        "extracted_variables": {
            "name": "Arthur Curry",
            "email": "arthur@atlantis.example",
            "summary": "Successful appointment booking.",
        },
    }
    res = test_client.post("/webhooks/dograh/call-ended", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "processed"
    assert data["call_id"] == "dograh_call_999"
