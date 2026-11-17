"""Agent definitions and implementations."""

from src.agents.base_agent import BaseVoiceAgent
from src.agents.inbound_booking_agent import InboundBookingAgent
from src.agents.outbound_lead_agent import OutboundLeadAgent
from src.agents.prompts import (
    INBOUND_BOOKING_SYSTEM_PROMPT,
    OUTBOUND_QUALIFICATION_SYSTEM_PROMPT,
    POST_CALL_SUMMARIZATION_PROMPT,
)

__all__ = [
    "BaseVoiceAgent",
    "InboundBookingAgent",
    "OutboundLeadAgent",
    "INBOUND_BOOKING_SYSTEM_PROMPT",
    "OUTBOUND_QUALIFICATION_SYSTEM_PROMPT",
    "POST_CALL_SUMMARIZATION_PROMPT",
]
