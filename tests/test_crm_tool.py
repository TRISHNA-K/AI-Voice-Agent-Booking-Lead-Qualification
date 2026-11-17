"""Unit tests for CRM Adapter."""

import asyncio


def test_crm_create_lookup_and_update(temp_crm_db):
    adapter = temp_crm_db

    # 1. Create Lead
    lead = asyncio.run(adapter.create_or_update_lead({
        "name": "Bruce Wayne",
        "email": "bruce@wayne-enterprises.example",
        "phone": "+15551239999",
        "company": "Wayne Enterprises",
        "status": "New Lead",
    }))
    assert lead["id"].startswith("lead_")
    assert lead["name"] == "Bruce Wayne"

    # 2. Lookup by phone
    found_by_phone = asyncio.run(adapter.lookup_lead(phone="+1 (555) 123-9999"))
    assert found_by_phone is not None
    assert found_by_phone["id"] == lead["id"]

    # 3. Lookup by email
    found_by_email = asyncio.run(adapter.lookup_lead(email="BRUCE@wayne-enterprises.example"))
    assert found_by_email is not None
    assert found_by_email["id"] == lead["id"]

    # 4. Update qualification
    updated = asyncio.run(adapter.update_qualification(
        lead_id=lead["id"],
        stage="Sales Qualified Lead (SQL)",
        score=95,
        bant_data={"budget": "approved", "authority": "CEO"},
        summary="High value enterprise deal.",
    ))
    assert updated["stage"] == "Sales Qualified Lead (SQL)"
    assert updated["lead_score"] == 95

    # 5. Log call
    call_log = asyncio.run(adapter.log_call(
        lead_id=lead["id"],
        call_direction="outbound",
        duration_seconds=120,
        summary="Successful discovery session.",
        transcript="Agent: Hello... User: Yes...",
        outcome="Appointment Booked",
        booking_id="cal_12345",
    ))
    assert call_log["outcome"] == "Appointment Booked"
    assert call_log["duration_seconds"] == 120
