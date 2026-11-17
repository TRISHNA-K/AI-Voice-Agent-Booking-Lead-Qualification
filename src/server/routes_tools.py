"""Tool execution API endpoints called by Dograh AI during active phone calls."""

from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.tools.calcom_tool import CalComTool
from src.tools.crm_tool import get_crm_adapter
from src.tools.telephony_tool import TelephonyTool
from src.utils.logger import get_logger

logger = get_logger("routes_tools")
router = APIRouter(prefix="/tools", tags=["Voice Agent Tools"])

calcom_client = CalComTool()
crm_client = get_crm_adapter()
telephony_client = TelephonyTool()


# Request Schemas
class CheckSlotsRequest(BaseModel):
    date_str: Optional[str] = Field(None, description="Spoken date preference, e.g. 'tomorrow afternoon'")
    max_options: int = Field(3, description="Maximum slots to offer")


class BookAppointmentRequest(BaseModel):
    start_time: str = Field(..., description="Chosen slot time in ISO or natural language")
    name: str = Field(..., description="Full name of attendee")
    email: str = Field(..., description="Email address for invite")
    notes: Optional[str] = Field(None, description="Meeting topic or inquiry notes")
    phone_number: Optional[str] = Field(None, description="Attendee phone number")


class CancelAppointmentRequest(BaseModel):
    booking_id: str
    reason: Optional[str] = "Cancelled via voice agent"


class LookupLeadRequest(BaseModel):
    phone: Optional[str] = None
    email: Optional[str] = None


class UpdateQualificationRequest(BaseModel):
    lead_id: str
    stage: str
    score: int
    bant_data: Dict[str, Any]
    summary: Optional[str] = None


class TransferCallRequest(BaseModel):
    transfer_reason: str
    caller_name: Optional[str] = None
    target_phone: Optional[str] = None


# Endpoints
@router.post("/calcom/check-slots")
async def check_available_slots(req: CheckSlotsRequest):
    """Query Cal.com availability and return conversational voice choices."""
    try:
        logger.info(f"Incoming tool call: check-slots for '{req.date_str}'")
        res = await calcom_client.get_speech_options(date_str=req.date_str, max_options=req.max_options)
        return res
    except Exception as exc:
        logger.error(f"Error checking slots: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/calcom/book-appointment")
async def book_appointment(req: BookAppointmentRequest):
    """Reserve appointment on Cal.com and update CRM record."""
    try:
        logger.info(f"Incoming tool call: book-appointment for {req.name} ({req.email}) at {req.start_time}")
        booking_result = await calcom_client.create_booking(
            start_time=req.start_time,
            name=req.name,
            email=req.email,
            notes=req.notes,
            phone_number=req.phone_number,
        )

        # Update CRM record with booking
        if booking_result.get("success"):
            await crm_client.create_or_update_lead({
                "name": req.name,
                "email": req.email,
                "phone": req.phone_number or "",
                "status": "Appointment Booked",
                "stage": "Sales Qualified Lead (SQL)",
                "notes": f"Appointment booked via Voice Agent for {booking_result.get('formatted_time')}",
            })

        return booking_result
    except Exception as exc:
        logger.error(f"Error booking appointment: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/calcom/cancel-appointment")
async def cancel_appointment(req: CancelAppointmentRequest):
    """Cancel existing Cal.com booking."""
    try:
        return await calcom_client.cancel_booking(booking_id=req.booking_id, reason=req.reason)
    except Exception as exc:
        logger.error(f"Error cancelling appointment: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/crm/lookup-lead")
async def lookup_lead(req: LookupLeadRequest):
    """Lookup contact details by phone or email in CRM."""
    lead = await crm_client.lookup_lead(phone=req.phone, email=req.email)
    if not lead:
        return {"found": False, "message": "Lead not found in CRM"}
    return {"found": True, "lead": lead}


@router.post("/crm/update-qualification")
async def update_qualification(req: UpdateQualificationRequest):
    """Save BANT evaluation score and lifecycle stage into CRM."""
    res = await crm_client.update_qualification(
        lead_id=req.lead_id,
        stage=req.stage,
        score=req.score,
        bant_data=req.bant_data,
        summary=req.summary,
    )
    return res


@router.post("/telephony/transfer-call")
async def transfer_call(req: TransferCallRequest):
    """Trigger telephony call transfer to live human specialist."""
    return await telephony_client.transfer_to_human(
        transfer_reason=req.transfer_reason,
        caller_name=req.caller_name,
        target_phone=req.target_phone,
    )
