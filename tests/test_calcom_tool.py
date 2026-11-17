"""Unit tests for Cal.com Tool."""

import asyncio
from datetime import datetime
import pytz
from src.tools.calcom_tool import CalComTool
from src.utils.date_parser import parse_spoken_datetime, format_slot_for_speech


def test_date_parser_relative_terms():
    tz = pytz.timezone("America/New_York")
    ref = tz.localize(datetime(2026, 11, 17, 10, 0))

    dt_tomorrow = parse_spoken_datetime("tomorrow at 2pm", reference_dt=ref)
    assert dt_tomorrow is not None
    assert dt_tomorrow.day == 18
    assert dt_tomorrow.hour == 14

    dt_friday = parse_spoken_datetime("Friday morning", reference_dt=ref)
    assert dt_friday is not None
    assert dt_friday.weekday() == 4  # Friday
    assert dt_friday.hour == 10


def test_format_slot_for_speech():
    tz = pytz.timezone("America/New_York")
    dt = tz.localize(datetime(2026, 11, 20, 14, 0))
    speech = format_slot_for_speech(dt)
    assert "Friday, November 20th at 2 PM Eastern" in speech


def test_calcom_slots_mock():
    tool = CalComTool(api_key="mock_key")
    slots = asyncio.run(tool.get_available_slots("tomorrow", days_ahead=2))
    assert len(slots) > 0
    assert "formatted_speech" in slots[0]
    assert "iso_time" in slots[0]


def test_calcom_speech_options():
    tool = CalComTool(api_key="mock_key")
    options = asyncio.run(tool.get_speech_options(date_str="next Monday", max_options=2))
    assert options["available"] is True
    assert len(options["slots"]) <= 2
    assert "openings" in options["speech"] or "opening" in options["speech"] or "few openings" in options["speech"]


def test_calcom_booking_and_cancellation():
    tool = CalComTool(api_key="mock_key")
    res = asyncio.run(tool.create_booking(
        start_time="tomorrow at 10am",
        name="Alice Wonderland",
        email="alice@wonderland.example",
        notes="General inquiry",
    ))
    assert res["success"] is True
    assert "booking_id" in res
    assert res["name"] == "Alice Wonderland"
    assert "alice@wonderland.example" in res["speech_confirmation"]

    # Cancel booking
    cancel_res = asyncio.run(tool.cancel_booking(booking_id=res["booking_id"]))
    assert cancel_res["success"] is True
