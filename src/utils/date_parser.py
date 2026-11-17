"""Natural language date and time parsing for conversational voice agents."""

import re
from datetime import datetime, timedelta, time
from typing import Optional, Tuple
from dateutil import parser as dt_parser
import pytz


def parse_spoken_datetime(
    spoken_text: str,
    reference_dt: Optional[datetime] = None,
    default_timezone: str = "America/New_York",
) -> Optional[datetime]:
    """
    Parse natural spoken conversational date and time into a timezone-aware datetime.
    
    Handles relative phrases:
    - 'today at 3pm'
    - 'tomorrow morning'
    - 'next Monday at 10:30 am'
    - 'Friday afternoon at 2'
    - standard ISO or month-day dates: 'November 20th at 2pm'
    """
    if not spoken_text:
        return None

    tz = pytz.timezone(default_timezone)
    if reference_dt is None:
        now = datetime.now(tz)
    else:
        now = reference_dt if reference_dt.tzinfo else tz.localize(reference_dt)

    text = spoken_text.lower().strip()
    
    # Clean up speech artifacts
    text = re.sub(r"\b(around|approx|approximately|at about|sharp|o'clock)\b", "", text)
    text = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()

    target_date = now.date()
    extracted_time: Optional[time] = None

    # Determine day offsets
    if "day after tomorrow" in text:
        target_date = now.date() + timedelta(days=2)
        text = text.replace("day after tomorrow", "")
    elif "tomorrow" in text:
        target_date = now.date() + timedelta(days=1)
        text = text.replace("tomorrow", "")
    elif "today" in text:
        target_date = now.date()
        text = text.replace("today", "")
    else:
        # Check weekdays (e.g., 'next monday', 'this friday', 'tuesday')
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for idx, day in enumerate(weekdays):
            if day in text:
                current_weekday = now.weekday()
                days_ahead = idx - current_weekday
                if "next " + day in text:
                    days_ahead += 7
                elif days_ahead <= 0:
                    days_ahead += 7  # Next upcoming occurrence
                target_date = now.date() + timedelta(days=days_ahead)
                text = re.sub(rf"\b(next|this)?\s*{day}\b", "", text)
                break

    # Determine time of day defaults if loose words used
    if "morning" in text and not re.search(r"\d+(:|\s*(am|pm))", text):
        extracted_time = time(10, 0)
    elif "noon" in text or "midday" in text:
        extracted_time = time(12, 0)
    elif "afternoon" in text and not re.search(r"\d+(:|\s*(am|pm))", text):
        extracted_time = time(14, 0)
    elif "evening" in text and not re.search(r"\d+(:|\s*(am|pm))", text):
        extracted_time = time(17, 0)

    # Parse explicit time (e.g., '3pm', '10:30 am', '2:00', '15:00')
    time_match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2)) if time_match.group(2) else 0
        meridiem = time_match.group(3)

        if meridiem == "pm" and hour < 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        elif not meridiem:
            # If no AM/PM provided and hour between 1 and 6, assume afternoon (business hours)
            if 1 <= hour <= 6:
                hour += 12

        if 0 <= hour <= 23 and 0 <= minute <= 59:
            extracted_time = time(hour, minute)

    # If date was not resolved yet by relative keywords, try dateutil parser
    if target_date == now.date() and not ("today" in spoken_text.lower()):
        try:
            parsed = dt_parser.parse(spoken_text, default=now, fuzzy=True)
            return parsed if parsed.tzinfo else tz.localize(parsed)
        except Exception:
            pass

    if extracted_time is None:
        # Default to 10:00 AM
        extracted_time = time(10, 0)

    combined_dt = datetime.combine(target_date, extracted_time)
    return tz.localize(combined_dt)


def format_slot_for_speech(dt: datetime, include_timezone: bool = True) -> str:
    """
    Format a datetime object into a warm, natural conversational phrasing for Voice AI.
    
    Example:
    'Tuesday, November 18th at 2:00 PM Eastern'
    """
    day_name = dt.strftime("%A")
    month_name = dt.strftime("%B")
    day_num = dt.day

    # Ordinal suffix (1st, 2nd, 3rd, 4th, ...)
    if 11 <= (day_num % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day_num % 10, "th")

    time_str = dt.strftime("%I:%M %p").lstrip("0")
    if time_str.endswith(":00 AM"):
        time_str = time_str.replace(":00 AM", " AM")
    elif time_str.endswith(":00 PM"):
        time_str = time_str.replace(":00 PM", " PM")

    speech = f"{day_name}, {month_name} {day_num}{suffix} at {time_str}"
    
    if include_timezone and dt.tzinfo:
        tz_abbr = dt.strftime("%Z")
        # Map common US timezone abbreviations for smoother speech
        tz_spoken_map = {
            "EST": "Eastern",
            "EDT": "Eastern",
            "CST": "Central",
            "CDT": "Central",
            "MST": "Mountain",
            "MDT": "Mountain",
            "PST": "Pacific",
            "PDT": "Pacific",
            "UTC": "UTC",
        }
        spoken_tz = tz_spoken_map.get(tz_abbr, tz_abbr)
        speech += f" {spoken_tz}"

    return speech
