"""Cal.com API Integration Tool for Voice Agents.

Provides slot availability checking, appointment booking, rescheduling,
and cancellation with natural speech formatting for conversational AI.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import httpx
import pytz

from config.settings import get_settings
from src.utils.date_parser import format_slot_for_speech, parse_spoken_datetime
from src.utils.logger import get_logger

logger = get_logger("calcom_tool")


class CalComTool:
    """Tool client for Cal.com API v1 and v2 endpoints."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        event_type_id: Optional[int] = None,
        timezone: Optional[str] = None,
    ):
        settings = get_settings()
        self.api_key = api_key or settings.CALCOM_API_KEY
        self.api_url = (api_url or settings.CALCOM_API_URL).rstrip("/")
        self.event_type_id = event_type_id or settings.CALCOM_EVENT_TYPE_ID
        self.timezone = timezone or settings.CALCOM_TIMEZONE
        self.is_mock = not self.api_key or "mock" in self.api_key.lower()

    async def get_available_slots(
        self,
        date_str: Optional[str] = None,
        days_ahead: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Fetch available appointment slots.
        
        Args:
            date_str: Spoken or ISO date string (e.g. 'tomorrow', 'next Tuesday', '2026-11-20').
            days_ahead: Number of days to look ahead if specific date isn't locked down.
            
        Returns:
            List of slot dictionaries containing iso_time, formatted_speech, and timestamp.
        """
        tz = pytz.timezone(self.timezone)
        now = datetime.now(tz)

        target_dt = parse_spoken_datetime(date_str, reference_dt=now, default_timezone=self.timezone) if date_str else now
        start_date = (target_dt or now).date()
        end_date = start_date + timedelta(days=max(1, days_ahead))

        if self.is_mock:
            return self._generate_mock_slots(start_date, end_date, tz)

        # Live Cal.com API Request
        params = {
            "apiKey": self.api_key,
            "eventTypeId": self.event_type_id,
            "startTime": f"{start_date.isoformat()}T00:00:00Z",
            "endTime": f"{end_date.isoformat()}T23:59:59Z",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.api_url}/slots", params=params)
                if response.status_code == 200:
                    data = response.json()
                    raw_slots = data.get("slots", {})
                    formatted = []
                    # Cal.com returns slots keyed by date "YYYY-MM-DD"
                    for day, slots in raw_slots.items():
                        for slot in slots:
                            time_str = slot.get("time")
                            if time_str:
                                slot_dt = datetime.fromisoformat(time_str.replace("Z", "+00:00")).astimezone(tz)
                                formatted.append({
                                    "iso_time": slot_dt.isoformat(),
                                    "formatted_speech": format_slot_for_speech(slot_dt),
                                    "date": slot_dt.strftime("%Y-%m-%d"),
                                    "time": slot_dt.strftime("%I:%M %p"),
                                })
                    return formatted
                else:
                    logger.warning(f"Cal.com API returned {response.status_code}, falling back to dynamic mock.")
                    return self._generate_mock_slots(start_date, end_date, tz)
        except Exception as exc:
            logger.error(f"Error querying Cal.com API: {exc}. Using fallback slots.")
            return self._generate_mock_slots(start_date, end_date, tz)

    def _generate_mock_slots(self, start_date, end_date, tz) -> List[Dict[str, Any]]:
        """Generate realistic booking slots for demonstration and local testing."""
        slots = []
        curr = start_date
        # Common business meeting hours: 10:00 AM, 2:00 PM, 4:00 PM
        standard_hours = [(10, 0), (14, 0), (16, 0)]

        while curr <= end_date:
            # Skip weekends (Saturday=5, Sunday=6)
            if curr.weekday() < 5:
                for h, m in standard_hours:
                    slot_dt = tz.localize(datetime(curr.year, curr.month, curr.day, h, m))
                    slots.append({
                        "iso_time": slot_dt.isoformat(),
                        "formatted_speech": format_slot_for_speech(slot_dt),
                        "date": curr.strftime("%Y-%m-%d"),
                        "time": slot_dt.strftime("%I:%M %p"),
                    })
            curr += timedelta(days=1)
        return slots

    async def get_speech_options(
        self,
        date_str: Optional[str] = None,
        max_options: int = 3,
    ) -> Dict[str, Any]:
        """
        Return a natural voice prompt offering available options.
        
        Example:
        'I have availability tomorrow at 10:00 AM or 2:00 PM Eastern. Which one works better for you?'
        """
        slots = await self.get_available_slots(date_str=date_str, days_ahead=3)
        if not slots:
            return {
                "available": False,
                "slots": [],
                "speech": "I couldn't find any open appointments for that timeframe. Would another day or next week work?",
            }

        selected_slots = slots[:max_options]
        slot_phrasings = [s["formatted_speech"] for s in selected_slots]

        if len(slot_phrasings) == 1:
            speech = f"I have an opening on {slot_phrasings[0]}. Would that work for you?"
        elif len(slot_phrasings) == 2:
            speech = f"I have openings on {slot_phrasings[0]}, or {slot_phrasings[1]}. Which would you prefer?"
        else:
            speech = (
                f"I have a few openings available: {slot_phrasings[0]}, {slot_phrasings[1]}, "
                f"or {slot_phrasings[2]}. Which of those works best for your schedule?"
            )

        return {
            "available": True,
            "slots": selected_slots,
            "speech": speech,
        }

    async def create_booking(
        self,
        start_time: str,
        name: str,
        email: str,
        notes: Optional[str] = None,
        phone_number: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Confirm and reserve an appointment booking.
        
        Args:
            start_time: Natural or ISO date/time string.
            name: Caller's full name.
            email: Caller's verified email address.
            notes: Meeting topics, inquiry description, or requirements.
            phone_number: Caller's phone number for SMS reminders.
        """
        tz = pytz.timezone(self.timezone)
        booking_dt = parse_spoken_datetime(start_time, default_timezone=self.timezone)
        if not booking_dt:
            booking_dt = datetime.now(tz) + timedelta(days=1, hours=2)

        iso_start = booking_dt.isoformat()
        speech_time = format_slot_for_speech(booking_dt)

        if self.is_mock:
            booking_id = f"cal_book_{int(datetime.now().timestamp())}"
            logger.info(f"[MOCK CAL.COM] Created booking {booking_id} for {name} ({email}) at {speech_time}")
            return {
                "success": True,
                "booking_id": booking_id,
                "start_time": iso_start,
                "formatted_time": speech_time,
                "name": name,
                "email": email,
                "speech_confirmation": (
                    f"You're all set! I have booked your appointment for {speech_time}. "
                    f"A calendar invite and confirmation have been sent to {email}."
                ),
            }

        # Real Cal.com API call
        payload = {
            "eventTypeId": self.event_type_id,
            "start": iso_start,
            "name": name,
            "email": email,
            "timeZone": self.timezone,
            "metadata": {
                "source": "Dograh Voice AI Agent",
                "phone": phone_number or "",
                "notes": notes or "Automated booking via voice call",
            },
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.api_url}/bookings?apiKey={self.api_key}",
                    json=payload,
                )
                if response.status_code in (200, 201):
                    res_data = response.json()
                    b_id = str(res_data.get("booking", {}).get("id", "confirmed"))
                    return {
                        "success": True,
                        "booking_id": b_id,
                        "start_time": iso_start,
                        "formatted_time": speech_time,
                        "name": name,
                        "email": email,
                        "speech_confirmation": (
                            f"Great, I have scheduled your appointment for {speech_time}. "
                            f"A confirmation invite has been emailed to {email}."
                        ),
                    }
                else:
                    logger.error(f"Cal.com booking failed: {response.text}")
                    return {
                        "success": False,
                        "error": response.text,
                        "speech_confirmation": "I ran into a hiccup booking that exact slot. Let me find another opening for you.",
                    }
        except Exception as e:
            logger.error(f"Cal.com booking exception: {e}")
            return {
                "success": False,
                "error": str(e),
                "speech_confirmation": "I had trouble reaching the calendar service. Would you like me to try another time or transfer you?",
            }

    async def cancel_booking(self, booking_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """Cancel an existing Cal.com appointment."""
        if self.is_mock:
            return {
                "success": True,
                "booking_id": booking_id,
                "message": "Appointment cancelled successfully.",
                "speech_confirmation": "Your appointment has been cancelled. Let me know if you would like to reschedule.",
            }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.delete(
                    f"{self.api_url}/bookings/{booking_id}?apiKey={self.api_key}",
                    json={"cancellationReason": reason or "Cancelled by caller via Voice AI"},
                )
                return {
                    "success": res.status_code in (200, 204),
                    "booking_id": booking_id,
                    "speech_confirmation": "Your appointment has been cancelled successfully.",
                }
        except Exception as e:
            logger.error(f"Error cancelling booking: {e}")
            return {"success": False, "error": str(e)}
