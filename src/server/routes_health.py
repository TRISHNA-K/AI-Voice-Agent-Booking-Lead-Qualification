"""System health check and diagnostic status routes."""

from datetime import datetime, timezone
from fastapi import APIRouter
from config.settings import get_settings
from src.tools.crm_tool import get_crm_adapter

router = APIRouter(tags=["System Health"])
settings = get_settings()
crm = get_crm_adapter()


@router.get("/health")
async def health_check():
    """System health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "integrations": {
            "dograh_ai": "ready",
            "cal_com": "ready",
            "crm_provider": settings.CRM_PROVIDER,
            "llm_provider": settings.LLM_PROVIDER,
        },
    }


@router.get("/api/v1/status")
async def platform_status():
    """Diagnostic platform status endpoint."""
    lead_count = 0
    if hasattr(crm, "_read_data"):
        data = crm._read_data()
        lead_count = len(data.get("contacts", []))
        booking_count = len(data.get("bookings", []))
    else:
        booking_count = 0

    return {
        "app_name": settings.APP_NAME,
        "company": settings.COMPANY_NAME,
        "inbound_agent": settings.AGENT_NAME,
        "calcom_event_type_id": settings.CALCOM_EVENT_TYPE_ID,
        "crm_records_loaded": lead_count,
        "calcom_bookings_recorded": booking_count,
    }
