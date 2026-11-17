"""Web Dashboard API Endpoints.

Provides unified REST APIs for dashboard metrics, AI agent testing/simulation,
CRM lead management, Cal.com appointment scheduling, and platform analytics.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from config.settings import get_settings
from src.agents.inbound_booking_agent import InboundBookingAgent
from src.agents.outbound_lead_agent import OutboundLeadAgent
from src.tools.calcom_tool import CalComTool
from src.tools.crm_tool import get_crm_adapter
from src.utils.logger import get_logger

logger = get_logger("routes_dashboard")
router = APIRouter(prefix="/api/dashboard", tags=["Web Dashboard"])

settings = get_settings()
crm = get_crm_adapter()
calcom = CalComTool()

# In-memory store for interactive agent sessions
_active_sessions: Dict[str, Any] = {}


class AgentMessageRequest(BaseModel):
    session_id: str = Field(..., description="Unique session identifier")
    agent_id: str = Field(..., description="'alex' (inbound) or 'jordan' (outbound)")
    message: str = Field(..., description="User voice or text utterance")
    lead_context: Optional[Dict[str, Any]] = None


class LeadCreateRequest(BaseModel):
    name: str
    email: Optional[str] = ""
    phone: Optional[str] = ""
    company: Optional[str] = "Independent"
    stage: Optional[str] = "Lead"
    lead_score: Optional[int] = 0
    notes: Optional[str] = ""


class AppointmentBookRequest(BaseModel):
    start_time: str
    name: str
    email: str
    phone: Optional[str] = ""
    notes: Optional[str] = ""


class AppointmentCancelRequest(BaseModel):
    booking_id: str
    reason: Optional[str] = "Cancelled via web dashboard"


@router.get("/metrics")
async def get_dashboard_metrics():
    """Compute high-level KPIs and business metrics."""
    data = crm._read_data() if hasattr(crm, "_read_data") else {"contacts": [], "bookings": []}
    contacts = data.get("contacts", [])
    bookings = data.get("bookings", [])

    total_leads = len(contacts)
    all_calls: List[Dict[str, Any]] = []
    for c in contacts:
        for cl in c.get("call_logs", []):
            cl_copy = dict(cl)
            cl_copy["contact_name"] = c.get("name")
            cl_copy["contact_id"] = c.get("id")
            all_calls.append(cl_copy)

    total_calls = len(all_calls)
    total_bookings = len(bookings)
    qualified_leads = sum(1 for c in contacts if c.get("stage") == "Sales Qualified Lead (SQL)" or (c.get("lead_score") or 0) >= 70)
    warm_leads = sum(1 for c in contacts if c.get("stage") == "Marketing Qualified Lead (MQL)")

    conversion_rate = round((total_bookings / max(total_calls, 1)) * 100, 1) if total_calls > 0 else 0.0
    qualification_rate = round((qualified_leads / max(total_leads, 1)) * 100, 1) if total_leads > 0 else 0.0

    avg_duration = 0
    if all_calls:
        avg_duration = round(sum(c.get("duration_seconds", 60) for c in all_calls) / len(all_calls))

    # Stage funnel breakdown
    stages = {"Lead": 0, "Marketing Qualified Lead (MQL)": 0, "Sales Qualified Lead (SQL)": 0, "Disqualified": 0}
    for c in contacts:
        st = c.get("stage", "Lead")
        if st in stages:
            stages[st] += 1
        else:
            stages["Lead"] += 1

    return {
        "kpis": {
            "total_calls": total_calls,
            "appointments_booked": total_bookings,
            "qualified_leads": qualified_leads,
            "warm_leads": warm_leads,
            "conversion_rate_percent": conversion_rate,
            "qualification_rate_percent": qualification_rate,
            "avg_call_duration_seconds": avg_duration,
        },
        "stage_funnel": stages,
        "recent_calls_count": len(all_calls),
    }


@router.get("/crm/leads")
async def list_crm_leads():
    """Retrieve full list of CRM contacts with detailed call records and scores."""
    data = crm._read_data() if hasattr(crm, "_read_data") else {"contacts": []}
    contacts = data.get("contacts", [])
    # Sort with newest/highest score first
    contacts_sorted = sorted(contacts, key=lambda x: (x.get("lead_score", 0), x.get("updated_at", "")), reverse=True)
    return {"leads": contacts_sorted, "count": len(contacts_sorted)}


@router.post("/crm/leads")
async def create_crm_lead(req: LeadCreateRequest):
    """Add a new contact to the CRM."""
    record = await crm.create_or_update_lead(req.model_dump())
    return {"success": True, "lead": record}


@router.get("/appointments")
async def list_appointments():
    """Retrieve confirmed bookings and upcoming Cal.com slot openings."""
    data = crm._read_data() if hasattr(crm, "_read_data") else {"bookings": []}
    bookings = data.get("bookings", [])

    # Fetch dynamic available slots for the next 3 business days
    upcoming_slots = await calcom.get_available_slots("tomorrow", days_ahead=3)

    return {
        "bookings": bookings,
        "upcoming_slots": upcoming_slots,
        "timezone": calcom.timezone,
        "event_type_id": calcom.event_type_id,
    }


@router.post("/appointments/book")
async def book_appointment_dashboard(req: AppointmentBookRequest):
    """Book appointment from web dashboard."""
    res = await calcom.create_booking(
        start_time=req.start_time,
        name=req.name,
        email=req.email,
        notes=req.notes,
        phone_number=req.phone,
    )
    if res.get("success"):
        await crm.create_or_update_lead({
            "name": req.name,
            "email": req.email,
            "phone": req.phone or "",
            "status": "Appointment Booked",
            "stage": "Sales Qualified Lead (SQL)",
            "notes": f"Dashboard Web Booking for {res.get('formatted_time')}",
        })
    return res


@router.post("/appointments/cancel")
async def cancel_appointment_dashboard(req: AppointmentCancelRequest):
    """Cancel existing Cal.com appointment."""
    return await calcom.cancel_booking(booking_id=req.booking_id, reason=req.reason)


@router.get("/calls")
async def list_call_history():
    """Retrieve all call logs with transcripts, outcomes, and duration."""
    data = crm._read_data() if hasattr(crm, "_read_data") else {"contacts": []}
    contacts = data.get("contacts", [])
    all_calls = []
    for c in contacts:
        for cl in c.get("call_logs", []):
            item = dict(cl)
            item["contact_id"] = c.get("id")
            item["contact_name"] = c.get("name")
            item["contact_email"] = c.get("email")
            item["contact_phone"] = c.get("phone")
            all_calls.append(item)

    all_calls.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return {"calls": all_calls, "count": len(all_calls)}


@router.post("/agent/chat")
async def agent_interactive_chat(req: AgentMessageRequest):
    """
    Interactive conversation turn with Alex (Inbound Booking) or Jordan (Outbound Lead Qual).
    Allows testing full voice flows in real time with tool executions returned.
    """
    session_key = f"{req.agent_id}_{req.session_id}"
    agent = _active_sessions.get(session_key)

    if not agent:
        if req.agent_id.lower() == "jordan":
            default_ctx = {
                "customer_name": "Prospect",
                "company": "Enterprise Corp",
                "phone": "+15554321098",
                "interest": "AI Voice Automation",
                "lead_id": f"lead_web_{req.session_id[:8]}",
            }
            if req.lead_context:
                default_ctx.update(req.lead_context)
            agent = OutboundLeadAgent(lead_context=default_ctx)
        else:
            agent = InboundBookingAgent()
        _active_sessions[session_key] = agent

    try:
        turn_result = await agent.process_turn(req.message)
        return {
            "session_id": req.session_id,
            "agent_id": req.agent_id,
            "speech": turn_result.get("speech", ""),
            "tool_calls": turn_result.get("tool_calls", []),
            "action": turn_result.get("action", "talk"),
            "score": turn_result.get("score"),
            "current_phase": getattr(agent, "current_phase", None),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        logger.error(f"Error in interactive chat for session {session_key}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/agent/reset")
async def agent_reset_session(session_id: str, agent_id: str):
    """Reset interactive agent session to start a fresh call."""
    session_key = f"{agent_id}_{session_id}"
    if session_key in _active_sessions:
        del _active_sessions[session_key]
    return {"status": "reset", "session_id": session_id}


@router.get("/settings")
async def get_system_settings():
    """Retrieve system configuration status with masked credentials."""
    s = get_settings()
    has_openai = s.has_valid_openai_key
    return {
        "app_name": s.APP_NAME,
        "company_name": s.COMPANY_NAME,
        "environment": s.APP_ENV,
        "debug": s.DEBUG,
        "agents": {
            "inbound": {"name": "Alex", "role": "Inbound Appointment Booking"},
            "outbound": {"name": "Jordan", "role": "Outbound BANT Qualification"},
        },
        "mode": {
            "ai_mode": "Live OpenAI" if has_openai else "Deterministic Mock / State Engine",
            "has_valid_openai_key": has_openai,
            "llm_model": s.LLM_MODEL,
        },
        "integrations": {
            "cal_com": {
                "status": "Connected (Mock)" if "mock" in s.CALCOM_API_KEY.lower() else "Connected (Live)",
                "timezone": s.CALCOM_TIMEZONE,
                "event_type_id": s.CALCOM_EVENT_TYPE_ID,
            },
            "crm": {
                "provider": s.CRM_PROVIDER,
                "database_file": s.CRM_DATABASE_FILE,
            },
            "dograh": {
                "inbound_workflow_id": s.DOGRAH_INBOUND_WORKFLOW_ID or "wf_inbound_booking_001",
                "outbound_workflow_id": s.DOGRAH_OUTBOUND_WORKFLOW_ID or "wf_outbound_lead_002",
                "telephony_provider": s.DOGRAH_TELEPHONY_PROVIDER,
            },
        },
    }
