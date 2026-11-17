"""Telephony actions for Dograh Voice Agents.

Handles warm transfers to human agents, voicemail detection (AMD),
and call termination.
"""

from typing import Any, Dict, Optional
from config.settings import get_settings
from src.utils.logger import get_logger

logger = get_logger("telephony_tool")


class TelephonyTool:
    """Telephony controller for live call manipulation."""

    def __init__(self):
        self.settings = get_settings()

    async def transfer_to_human(
        self,
        transfer_reason: str,
        caller_name: Optional[str] = None,
        target_phone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Initiate warm or cold transfer to a human specialist.
        
        Args:
            transfer_reason: Explanation of why transfer was initiated.
            caller_name: Name of caller.
            target_phone: Destination phone number.
        """
        dest_number = target_phone or self.settings.HUMAN_ESCALATION_PHONE_NUMBER
        logger.info(f"Initiating call transfer to {dest_number}. Reason: {transfer_reason}")

        return {
            "status": "transfer_initiated",
            "destination_number": dest_number,
            "caller_name": caller_name or "Caller",
            "reason": transfer_reason,
            "speech": (
                "I completely understand. Let me connect you directly with one of our specialists. "
                "Please hold on for just a moment while I transfer you."
            ),
        }

    async def handle_answering_machine(self, lead_name: str, callback_number: str) -> Dict[str, Any]:
        """
        Action taken when Dograh Answering Machine Detection (AMD) identifies voicemail.
        """
        message = (
            f"Hi {lead_name}, this is {self.settings.AGENT_NAME} with {self.settings.COMPANY_NAME}. "
            f"I'm reaching out regarding your recent inquiry. Please give us a call back at {callback_number} "
            f"or check your email to schedule a quick consultation. Have a great day!"
        )
        logger.info(f"AMD triggered: Voicemail dropped for {lead_name}")
        return {
            "status": "voicemail_dropped",
            "message": message,
            "end_call": True,
        }
