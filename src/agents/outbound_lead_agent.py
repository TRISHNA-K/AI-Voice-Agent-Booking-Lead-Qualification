"""Outbound Lead Qualification Voice AI Agent.

Conducts context-aware discovery calls using the BANT qualification framework,
scores leads dynamically, and auto-schedules discovery meetings on Cal.com.
"""

from typing import Any, Dict, List, Optional
from config.settings import get_settings
from src.agents.base_agent import BaseVoiceAgent
from src.agents.prompts import OUTBOUND_QUALIFICATION_SYSTEM_PROMPT
from src.tools.calcom_tool import CalComTool
from src.tools.crm_tool import get_crm_adapter
from src.tools.qualification_engine import BANTParameters, QualificationEngine, QualificationResult
from src.utils.logger import get_logger

logger = get_logger("outbound_agent")


class OutboundLeadAgent(BaseVoiceAgent):
    """Voice AI Agent for outbound lead qualification and meeting scheduling."""

    def __init__(self, lead_context: Optional[Dict[str, Any]] = None):
        super().__init__(name="Jordan", system_prompt=OUTBOUND_QUALIFICATION_SYSTEM_PROMPT)
        self.calcom = CalComTool()
        self.crm = get_crm_adapter()
        self.qual_engine = QualificationEngine()

        self.lead_context = lead_context or {
            "customer_name": "Prospect",
            "company": "Company",
            "phone": "",
            "interest": "AI Voice Automation",
            "lead_id": "lead_demo",
        }

        # Track conversational phase: 'greeting', 'need', 'authority', 'timeline', 'budget', 'closing'
        self.current_phase = "greeting"
        self.bant = BANTParameters()
        self.qualification_result: Optional[QualificationResult] = None

        self._init_tools()
        self.reset_conversation(context=self.lead_context)

    def _init_tools(self):
        """Register tools available to the outbound agent."""
        self.register_tool(
            name="check_available_slots",
            func=self.calcom.get_speech_options,
            definition={
                "name": "check_available_slots",
                "description": "Check available discovery demo slots on Cal.com.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date_str": {"type": "string", "description": "Preferred day or time."},
                    },
                },
            },
        )

        self.register_tool(
            name="book_discovery_call",
            func=self.calcom.create_booking,
            definition={
                "name": "book_discovery_call",
                "description": "Book a live discovery and demo session on Cal.com.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start_time": {"type": "string", "description": "Selected slot time."},
                        "name": {"type": "string", "description": "Prospect full name."},
                        "email": {"type": "string", "description": "Prospect email address."},
                        "notes": {"type": "string", "description": "Key pain points and requirements."},
                    },
                    "required": ["start_time", "name", "email"],
                },
            },
        )

        self.register_tool(
            name="update_crm_lead",
            func=self.crm.update_qualification,
            definition={
                "name": "update_crm_lead",
                "description": "Update CRM with qualification stage, score, and notes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "lead_id": {"type": "string", "description": "CRM lead identifier."},
                        "stage": {"type": "string", "description": "Target lifecycle stage."},
                        "score": {"type": "integer", "description": "Calculated BANT score."},
                        "bant_data": {"type": "object", "description": "BANT parameter values."},
                        "summary": {"type": "string", "description": "Summary notes."},
                    },
                    "required": ["lead_id", "stage", "score", "bant_data"],
                },
            },
        )

    def get_initial_greeting(self) -> str:
        """Produce the opening conversational statement upon telephony connection."""
        c_name = self.lead_context.get("customer_name", "there")
        return (
            f"Hi {c_name}, this is {self.name} calling from {self.settings.COMPANY_NAME}. "
            f"I noticed your interest in our AI voice booking solutions. "
            f"Did I catch you at an okay time for a quick two-minute chat?"
        )

    async def process_turn(self, user_utterance: str) -> Dict[str, Any]:
        """Process prospect utterance and move through qualification phases."""
        self.conversation_history.append({"role": "user", "content": user_utterance})
        text = user_utterance.lower().strip()
        executed_tools = []

        # Busy / Bad time deflection
        if any(w in text for w in ["busy", "not a good time", "in a meeting", "bad time", "call back later"]):
            speech = (
                "No problem at all! I will send you a quick follow-up note by email with a direct booking link "
                "so you can pick a time that suits your schedule. Thanks for your time and have a wonderful day!"
            )
            self.conversation_history.append({"role": "assistant", "content": speech})
            return {"speech": speech, "tool_calls": [], "action": "reschedule"}

        # Not interested / Hard objection
        if any(w in text for w in ["not interested", "stop calling", "remove me", "don't need this"]):
            self.qualification_result = self.qual_engine.evaluate(self.bant)
            await self.crm.update_qualification(
                lead_id=self.lead_context.get("lead_id", "unknown"),
                stage="Disqualified",
                score=10,
                bant_data=self.bant.model_dump(),
                summary="Prospect declined: Not interested.",
            )
            speech = "Understood! Thank you for letting me know, and have a great rest of your day."
            self.conversation_history.append({"role": "assistant", "content": speech})
            return {"speech": speech, "tool_calls": [], "action": "disqualified"}

        # Phase 1: Greeting Handshake
        if self.current_phase == "greeting":
            self.current_phase = "need"
            speech = (
                "Great! To start, what is currently the biggest challenge you face with your customer appointments "
                "or inbound phone calls?"
            )
            self.conversation_history.append({"role": "assistant", "content": speech})
            return {"speech": speech, "tool_calls": [], "action": "ask_need"}

        # Phase 2: Need Discovery
        if self.current_phase == "need":
            self.bant.need_pain_point = user_utterance
            self.bant.need_urgency = "high" if any(w in text for w in ["losing", "lose", "missed", "missing", "miss", "overwhelmed", "bottleneck", "urgent", "problem", "too many", "drop"]) else "medium"
            self.current_phase = "authority"
            speech = (
                "That makes complete sense, and a lot of teams we work with struggled with that exact issue. "
                "Are you leading the evaluation for this initiative yourself, or are other stakeholders involved?"
            )
            self.conversation_history.append({"role": "assistant", "content": speech})
            return {"speech": speech, "tool_calls": [], "action": "ask_authority"}

        # Phase 3: Authority Discovery
        if self.current_phase == "authority":
            self.bant.authority_role = user_utterance
            self.bant.is_decision_maker = any(w in text for w in ["me", "myself", "i am", "founder", "ceo", "director", "vp", "owner", "decision maker"])
            self.current_phase = "timeline"
            speech = "Understood. When are you looking to have an AI voice solution up and running?"
            self.conversation_history.append({"role": "assistant", "content": speech})
            return {"speech": speech, "tool_calls": [], "action": "ask_timeline"}

        # Phase 4: Timeline Discovery
        if self.current_phase == "timeline":
            self.bant.timeline_phrase = user_utterance
            self.bant.timeline_months = 1 if any(w in text for w in ["immediately", "asap", "this month", "right now"]) else 3
            self.current_phase = "budget"
            speech = "Got it. Do you already have a budget allocated for this project this year?"
            self.conversation_history.append({"role": "assistant", "content": speech})
            return {"speech": speech, "tool_calls": [], "action": "ask_budget"}

        # Phase 5: Budget Discovery & Final Scoring / Booking Transition
        if self.current_phase == "budget":
            self.bant.budget_range = user_utterance
            self.bant.budget_approved = any(w in text for w in ["yes", "approved", "allocated", "have budget", "we do"])
            self.qualification_result = self.qual_engine.evaluate(self.bant)
            self.current_phase = "closing"

            # Sync with CRM
            await self.crm.update_qualification(
                lead_id=self.lead_context.get("lead_id", "lead_demo"),
                stage=self.qualification_result.stage,
                score=self.qualification_result.total_score,
                bant_data=self.bant.model_dump(),
                summary=self.qualification_result.qualification_notes,
            )

            # Route based on score
            if self.qualification_result.recommended_action == "book_meeting":
                # Check Cal.com slots
                slots_info = await self.calcom.get_speech_options(date_str="tomorrow", max_options=2)
                executed_tools.append({"tool": "check_available_slots", "result": slots_info})

                speech = (
                    f"Thanks for sharing that! Based on your goals, our solutions team can show you a live demo "
                    f"tailored to {self.lead_context.get('company', 'your company')}. "
                    f"{slots_info['speech']}"
                )
                self.conversation_history.append({"role": "assistant", "content": speech})
                return {"speech": speech, "tool_calls": executed_tools, "action": "offer_booking", "score": self.qualification_result.total_score}
            else:
                speech = (
                    f"Thank you for sharing your background! I've noted down your requirements and our team will "
                    f"send tailored resources to your email. Have a great rest of your week!"
                )
                self.conversation_history.append({"role": "assistant", "content": speech})
                return {"speech": speech, "tool_calls": executed_tools, "action": "nurture", "score": self.qualification_result.total_score}

        # Phase 6: Closing & Final Booking Execution
        if self.current_phase == "closing":
            if any(w in text for w in ["first", "second", "tomorrow", "sounds good", "works", "yes", "sure", "10", "2", "4"]):
                # Reserve appointment
                book_res = await self.calcom.create_booking(
                    start_time="tomorrow at 2pm",
                    name=self.lead_context.get("customer_name", "Lead"),
                    email=self.lead_context.get("email", "lead@company.example"),
                    notes=f"Discovery Demo: {self.bant.need_pain_point}",
                    phone_number=self.lead_context.get("phone"),
                )
                executed_tools.append({"tool": "book_discovery_call", "result": book_res})

                speech = (
                    f"Fantastic! You are confirmed for our discovery walkthrough. "
                    f"A calendar invite has been sent over to your email. Looking forward to speaking soon!"
                )
                self.conversation_history.append({"role": "assistant", "content": speech})
                return {"speech": speech, "tool_calls": executed_tools, "action": "booking_completed"}

        # Generic closing fallback
        speech = "Thank you so much for your time today. We look forward to working with you. Goodbye!"
        self.conversation_history.append({"role": "assistant", "content": speech})
        return {"speech": speech, "tool_calls": [], "action": "ended"}
