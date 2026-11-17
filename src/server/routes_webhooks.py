"""Webhook endpoints for Dograh post-call analysis and Cal.com event synchronization."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from config.settings import get_settings
from src.tools.crm_tool import get_crm_adapter
from src.utils.logger import get_logger

logger = get_logger("routes_webhooks")
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])
crm_client = get_crm_adapter()


class DograhCallEndedPayload(BaseModel):
    call_id: str
    direction: str = "inbound"  # 'inbound' or 'outbound'
    duration_seconds: int = 60
    phone_number: Optional[str] = None
    transcript: str = ""
    extracted_variables: Dict[str, Any] = Field(default_factory=dict)
    recording_url: Optional[str] = None
    outcome: Optional[str] = None
    lead_id: Optional[str] = None


class CalComWebhookPayload(BaseModel):
    triggerEvent: str
    payload: Dict[str, Any] = Field(default_factory=dict)


@router.post("/dograh/call-ended")
async def handle_dograh_call_ended(payload: DograhCallEndedPayload):
    """
    Handle post-call webhook emitted by Dograh when a voice call terminates.
    Extracts summary, updates CRM records, and logs call engagement.
    """
    logger.info(f"Received Dograh Call Ended webhook for call_id={payload.call_id} ({payload.direction})")

    # Determine or lookup lead ID
    lead_id = payload.lead_id
    if not lead_id and payload.phone_number:
        existing = await crm_client.lookup_lead(phone=payload.phone_number)
        if existing:
            lead_id = existing.get("id")

    # If lead not in CRM, create from extracted variables or phone
    if not lead_id:
        new_lead = await crm_client.create_or_update_lead({
            "phone": payload.phone_number or "+15550000000",
            "name": payload.extracted_variables.get("name", "Caller"),
            "email": payload.extracted_variables.get("email", ""),
            "notes": f"Captured from Dograh voice call {payload.call_id}",
        })
        lead_id = new_lead.get("id")

    # Heuristic / fallback intelligence extraction
    summary = payload.extracted_variables.get("summary")
    if not summary:
        if "booked" in payload.transcript.lower() or "confirmed" in payload.transcript.lower():
            summary = "Caller successfully scheduled an appointment on the calendar."
            outcome = "Appointment Booked"
        elif "cancel" in payload.transcript.lower():
            summary = "Caller requested cancellation or rescheduling."
            outcome = "Appointment Cancelled"
        elif "transfer" in payload.transcript.lower():
            summary = "Call escalated to a live human representative."
            outcome = "Call Transferred"
        else:
            summary = "General inquiry and conversation completed."
            outcome = "Call Completed"
    else:
        outcome = payload.outcome or "Completed"

    booking_id = payload.extracted_variables.get("booking_id")

    # Log to CRM
    log_result = await crm_client.log_call(
        lead_id=lead_id,
        call_direction=payload.direction,
        duration_seconds=payload.duration_seconds,
        summary=summary,
        transcript=payload.transcript,
        outcome=outcome,
        recording_url=payload.recording_url,
        booking_id=booking_id,
    )

    return {
        "status": "processed",
        "call_id": payload.call_id,
        "lead_id": lead_id,
        "summary": summary,
        "outcome": outcome,
        "crm_log": log_result,
    }


@router.post("/calcom/booking-event")
async def handle_calcom_webhook(request: Request):
    """Synchronize Cal.com calendar events (booking created, rescheduled, cancelled)."""
    try:
        body = await request.json()
        event_type = body.get("triggerEvent", "UNKNOWN")
        payload = body.get("payload", {})
        logger.info(f"Received Cal.com webhook: {event_type}")

        attendees = payload.get("attendees", [])
        email = attendees[0].get("email") if attendees else payload.get("email")
        name = attendees[0].get("name") if attendees else payload.get("name")

        if email:
            contact = await crm_client.lookup_lead(email=email)
            if contact:
                lead_id = contact.get("id")
                await crm_client.update_qualification(
                    lead_id=lead_id,
                    stage="Sales Qualified Lead (SQL)",
                    score=90,
                    bant_data={"booking_event": event_type, "booking_time": payload.get("startTime")},
                    summary=f"Cal.com Webhook Sync: {event_type} at {payload.get('startTime')}",
                )

        return {"status": "synced", "event": event_type}
    except Exception as exc:
        logger.error(f"Error processing Cal.com webhook: {exc}")
        return {"status": "error", "detail": str(exc)}
