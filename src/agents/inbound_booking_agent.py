"""Inbound Appointment Booking Voice AI Agent.

Handles incoming customer calls for scheduling, slot checking, and rescheduling
with real-time Cal.com and CRM integration.
"""

import re
from typing import Any, Dict, List, Optional
from config.settings import get_settings
from src.agents.base_agent import BaseVoiceAgent
from src.agents.prompts import INBOUND_BOOKING_SYSTEM_PROMPT
from src.tools.calcom_tool import CalComTool
from src.tools.crm_tool import get_crm_adapter
from src.tools.telephony_tool import TelephonyTool
from src.utils.logger import get_logger

logger = get_logger("inbound_agent")


class InboundBookingAgent(BaseVoiceAgent):
    """Inbound Voice AI Agent for appointment scheduling and inquiries."""

    def __init__(self):
        super().__init__(name="Alex", system_prompt=INBOUND_BOOKING_SYSTEM_PROMPT)
        self.calcom = CalComTool()
        self.crm = get_crm_adapter()
        self.telephony = TelephonyTool()

        # Ephemeral call state tracking
        self.caller_info: Dict[str, Any] = {
            "name": None,
            "email": None,
            "phone": None,
            "service": None,
            "selected_slot": None,
            "booking_id": None,
        }

        self._init_tools()
        self.reset_conversation()

    def _init_tools(self):
        """Register tool schemas for Dograh and LLM function calling."""
        self.register_tool(
            name="check_available_slots",
            func=self.calcom.get_speech_options,
            definition={
                "name": "check_available_slots",
                "description": "Check real-time calendar availability and retrieve available appointment slots.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date_str": {
                            "type": "string",
                            "description": "Spoken date/time preference, e.g. 'tomorrow', 'next Tuesday', 'Friday morning'.",
                        },
                        "max_options": {
                            "type": "integer",
                            "description": "Number of alternative slots to present to the caller (default 3).",
                        },
                    },
                },
            },
        )

        self.register_tool(
            name="book_appointment",
            func=self.calcom.create_booking,
            definition={
                "name": "book_appointment",
                "description": "Confirm and book an appointment slot on Cal.com and update the CRM.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start_time": {
                            "type": "string",
                            "description": "Chosen slot time (spoken format or ISO timestamp).",
                        },
                        "name": {"type": "string", "description": "Caller full name."},
                        "email": {"type": "string", "description": "Caller email address."},
                        "notes": {"type": "string", "description": "Meeting topics or notes."},
                    },
                    "required": ["start_time", "name", "email"],
                },
            },
        )

        self.register_tool(
            name="cancel_appointment",
            func=self.calcom.cancel_booking,
            definition={
                "name": "cancel_appointment",
                "description": "Cancel or delete an existing appointment on Cal.com.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "booking_id": {"type": "string", "description": "Cal.com booking identifier."},
                        "reason": {"type": "string", "description": "Reason for cancellation."},
                    },
                    "required": ["booking_id"],
                },
            },
        )

        self.register_tool(
            name="transfer_to_human",
            func=self.telephony.transfer_to_human,
            definition={
                "name": "transfer_to_human",
                "description": "Transfer caller to a human agent when they request live support or escalation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "transfer_reason": {"type": "string", "description": "Reason for escalating to human."},
                        "caller_name": {"type": "string", "description": "Caller name if known."},
                    },
                    "required": ["transfer_reason"],
                },
            },
        )

    def extract_caller_entities(self, text: str):
        """Heuristic entity extraction from user utterance."""
        # Email extraction
        email_match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
        if email_match:
            self.caller_info["email"] = email_match.group(0).rstrip(".,;:!?'\"").lower()

        # Spoken email extraction e.g. "john dot doe at gmail dot com"
        spoken_email = re.search(r"([a-zA-Z0-9]+)\s+dot\s+([a-zA-Z0-9]+)\s+at\s+([a-zA-Z0-9]+)\s+dot\s+(com|org|io|net)", text.lower())
        if spoken_email:
            self.caller_info["email"] = f"{spoken_email.group(1)}.{spoken_email.group(2)}@{spoken_email.group(3)}.{spoken_email.group(4)}"

        # Name extraction patterns: "my name is X", "I am X", "this is X"
        name_match = re.search(r"(?:my name is|i am|this is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", text, re.IGNORECASE)
        if name_match:
            self.caller_info["name"] = name_match.group(1).title()

    async def process_turn(self, user_utterance: str) -> Dict[str, Any]:
        """Process conversational turn using LLM tool calling or state machine engine."""
        self.conversation_history.append({"role": "user", "content": user_utterance})
        self.extract_caller_entities(user_utterance)

        # Check if OpenAI API key is set for live LLM execution
        settings = get_settings()
        if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.startswith("sk-"):
            return await self._process_with_openai(user_utterance)

        # High-precision conversational state machine engine for offline/testing/mock mode
        return await self._process_with_state_engine(user_utterance)

    async def _process_with_state_engine(self, user_utterance: str) -> Dict[str, Any]:
        """Deterministic, voice-optimized conversational engine."""
        text = user_utterance.lower().strip()
        executed_tools = []

        # 0. Wrap up if already booked
        if self.caller_info.get("booking_id") and any(w in text for w in ["thank", "thanks", "that's all", "bye", "goodbye", "all set"]):
            speech = f"You're very welcome! Have a wonderful day, and we look forward to speaking with you. Goodbye!"
            self.conversation_history.append({"role": "assistant", "content": speech})
            return {"speech": speech, "tool_calls": [], "action": "ended"}

        # 1. Escalation / Human Transfer Request
        if any(w in text for w in ["human", "representative", "agent", "real person", "operator", "speak to someone"]):
            res = await self.telephony.transfer_to_human(
                transfer_reason="Caller requested human representative",
                caller_name=self.caller_info.get("name"),
            )
            executed_tools.append({"tool": "transfer_to_human", "result": res})
            speech = res["speech"]
            self.conversation_history.append({"role": "assistant", "content": speech})
            return {"speech": speech, "tool_calls": executed_tools, "action": "transfer"}

        # 2. Cancellation Request
        if any(w in text for w in ["cancel", "delete appointment", "cancel booking"]):
            res = await self.calcom.cancel_booking(
                booking_id=self.caller_info.get("booking_id") or "cal_book_default",
                reason="Caller requested cancellation",
            )
            executed_tools.append({"tool": "cancel_appointment", "result": res})
            speech = res["speech_confirmation"]
            self.conversation_history.append({"role": "assistant", "content": speech})
            return {"speech": speech, "tool_calls": executed_tools, "action": "cancelled"}

        # 3. Booking Confirmation Intent (Caller provides/confirms time and contact info)
        has_time_phrase = any(w in text for w in ["tomorrow", "monday", "tuesday", "wednesday", "thursday", "friday", "am", "pm", "at 10", "at 2", "at 4", "first option", "second option"])
        has_contact_info = self.caller_info.get("email") is not None or "@" in text or "email" in text or "my name is" in text

        if self.caller_info.get("selected_slot") and has_contact_info:
            name = self.caller_info.get("name") or "Valued Customer"
            email = self.caller_info.get("email") or "customer@example.com"
            slot = self.caller_info["selected_slot"]

            booking_res = await self.calcom.create_booking(
                start_time=slot,
                name=name,
                email=email,
                notes=f"Inbound booking for {name}",
                phone_number=self.caller_info.get("phone"),
            )
            executed_tools.append({"tool": "book_appointment", "result": booking_res})
            self.caller_info["booking_id"] = booking_res.get("booking_id")

            # Update CRM record
            await self.crm.create_or_update_lead({
                "name": name,
                "email": email,
                "phone": self.caller_info.get("phone", ""),
                "stage": "Sales Qualified Lead (SQL)",
                "status": "Appointment Booked",
                "notes": f"Booked via Voice Agent for {booking_res.get('formatted_time')}",
            })

            speech = booking_res.get("speech_confirmation")
            self.conversation_history.append({"role": "assistant", "content": speech})
            return {"speech": speech, "tool_calls": executed_tools, "action": "booked"}

        # 4. Check Availability / Scheduling Intent
        if any(w in text for w in ["book", "schedule", "appointment", "consultation", "time", "available", "openings", "tomorrow", "next week", "friday"]):
            options = await self.calcom.get_speech_options(date_str=text)
            executed_tools.append({"tool": "check_available_slots", "result": options})

            if options["slots"]:
                self.caller_info["selected_slot"] = options["slots"][0]["iso_time"]

            # If we don't have their name or email yet, prompt for it naturally
            if not self.caller_info.get("name") or not self.caller_info.get("email"):
                speech = f"{options['speech']} To lock that in, may I have your full name and email address?"
            else:
                speech = options["speech"]

            self.conversation_history.append({"role": "assistant", "content": speech})
            return {"speech": speech, "tool_calls": executed_tools, "action": "slots_offered"}

        # 5. Greeting / General Intro
        if any(w in text for w in ["hello", "hi", "hey", "good morning", "good afternoon"]):
            speech = (
                f"Hello! Thank you for calling {self.settings.COMPANY_NAME}. "
                f"My name is {self.name}. Are you looking to schedule a new appointment or manage an existing one?"
            )
            self.conversation_history.append({"role": "assistant", "content": speech})
            return {"speech": speech, "tool_calls": [], "action": "greet"}

        # 6. Fallback General Helpful Turn
        speech = (
            "I'm here to help you get scheduled with our team. "
            "What day of the week or time generally works best for you?"
        )
        self.conversation_history.append({"role": "assistant", "content": speech})
        return {"speech": speech, "tool_calls": [], "action": "clarify"}

    async def _process_with_openai(self, user_utterance: str) -> Dict[str, Any]:
        """Live LLM execution with native tool calling via OpenAI API."""
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self.settings.OPENAI_API_KEY)

            tools_param = [{"type": "function", "function": t} for t in self.tool_definitions]

            response = await client.chat.completions.create(
                model=self.settings.LLM_MODEL,
                messages=self.conversation_history,
                tools=tools_param,
                temperature=self.settings.LLM_TEMPERATURE,
            )

            msg = response.choices[0].message
            executed_tools = []

            if msg.tool_calls:
                for tool_call in msg.tool_calls:
                    fn_name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)
                    logger.info(f"LLM triggered tool: {fn_name} with {args}")

                    tool_fn = self.tools.get(fn_name)
                    if tool_fn:
                        res = await tool_fn(**args)
                        executed_tools.append({"tool": fn_name, "result": res})

                # Follow-up generation after tool execution
                speech = executed_tools[0]["result"].get("speech_confirmation") or executed_tools[0]["result"].get("speech") or "I've handled that for you."
            else:
                speech = msg.content or "How else can I assist you with your appointment today?"

            self.conversation_history.append({"role": "assistant", "content": speech})
            return {"speech": speech, "tool_calls": executed_tools, "action": "llm_turn"}

        except Exception as e:
            logger.error(f"OpenAI turn processing error: {e}. Falling back to state engine.")
            return await self._process_with_state_engine(user_utterance)
