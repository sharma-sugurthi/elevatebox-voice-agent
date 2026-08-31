"""
app/scheduler.py — parse vague spoken callback times into real datetimes.

The LLM extracts the raw phrase ("tomorrow morning") into callback_phrase.
This module converts that into an actual datetime and a confirmation string.

All logic is deterministic Python — no LLM calls here.
The LLM is bad at date arithmetic; Python is reliable and free.
"""

from datetime import datetime, time, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# ── Time-of-day lookup table ───────────────────────────────────────────────────
# Maps common spoken time words → a clock time (IST)
TIME_OF_DAY: dict[str, time] = {
    "morning":     time(10, 0),
    "afternoon":   time(14, 0),
    "after lunch": time(14, 0),
    "lunch":       time(14, 0),
    "evening":     time(18, 0),
    "night":       time(20, 0),
    "tonight":     time(20, 0),
}

# ── In-memory booking store ────────────────────────────────────────────────────
# call_id → confirmed datetime
_bookings: dict[str, datetime] = {}


def _resolve_day_offset(phrase: str, now: datetime) -> int:
    """
    Extract how many days from now the callback should be.
    Returns 0 for today, 1 for tomorrow, 7 for next week, etc.
    """
    phrase_lower = phrase.lower()

    if "day after tomorrow" in phrase_lower:
        return 2
    if "tomorrow" in phrase_lower:
        return 1
    if "next week" in phrase_lower:
        # Monday of next week
        days_until_monday = (7 - now.weekday()) % 7
        return days_until_monday if days_until_monday > 0 else 7
    if "today" in phrase_lower or "now" in phrase_lower:
        return 0

    # No explicit day mentioned — check if the implied time-of-day is still
    # in the future today. If yes, use today (0). Otherwise tomorrow (1).
    for key, t in TIME_OF_DAY.items():
        if key in phrase_lower:
            proposed = now.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
            return 0 if proposed > now else 1

    # No day or time keyword at all — default to tomorrow
    return 1


def _resolve_time_of_day(phrase: str, now: datetime, day_offset: int) -> time:
    """
    Find the best time-of-day match in the phrase.
    If the resolved time is in the past for today, returns a default of 10am.
    """
    phrase_lower = phrase.lower()

    # Check multi-word patterns first (order matters)
    for key in ["after lunch", "day after tomorrow"]:
        if key in phrase_lower and key in TIME_OF_DAY:
            return TIME_OF_DAY[key]

    # Then single-word patterns
    for key, t in TIME_OF_DAY.items():
        if key in phrase_lower:
            # If today and the time has already passed, the caller means tomorrow
            if day_offset == 0:
                proposed = now.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
                if proposed <= now:
                    return t   # caller says "today evening" at 7pm → still use 8pm
            return t

    # No time-of-day keyword found — default to 10am
    return time(10, 0)


def parse_callback_time(phrase: str, now: Optional[datetime] = None) -> Optional[datetime]:
    """
    Convert a vague spoken phrase into a concrete datetime.

    Examples:
        "tomorrow morning"          → next day at 10:00
        "call me after lunch"       → today or tomorrow at 14:00
        "evening sometime"          → today or tomorrow at 18:00
        "next week"                 → Monday of next week at 10:00
        "day after tomorrow"        → two days from now at 10:00

    Args:
        phrase: The raw string the callee spoke (from LLM's callback_phrase field).
        now: Override current time (for testing). Defaults to datetime.now().

    Returns:
        A concrete datetime, or None if parsing completely fails.
    """
    if not phrase:
        return None

    if now is None:
        now = datetime.now()

    try:
        day_offset = _resolve_day_offset(phrase, now)
        target_time = _resolve_time_of_day(phrase, now, day_offset)
        target_date = (now + timedelta(days=day_offset)).date()
        result = datetime(
            year=target_date.year,
            month=target_date.month,
            day=target_date.day,
            hour=target_time.hour,
            minute=target_time.minute,
            second=0,
        )
        logger.info(f"[scheduler] '{phrase}' → {result.strftime('%Y-%m-%d %H:%M')}")
        return result

    except Exception as e:
        logger.error(f"[scheduler] Failed to parse '{phrase}': {e}")
        return None


def format_confirmation(dt: datetime, now: Optional[datetime] = None) -> str:
    """
    Format a datetime into a natural spoken confirmation string.
    The agent speaks this out loud to confirm the booking with the caller.

    Example: datetime(2026, 8, 27, 10, 0) → "So around 10am tomorrow, August 27th?"

    Args:
        dt: The callback datetime to format.
        now: Override current time (for testing). Defaults to datetime.now().
    """
    if now is None:
        now = datetime.now()

    today = now.date()
    tomorrow = today + timedelta(days=1)
    target_date = dt.date()

    # Day label
    if target_date == today:
        day_label = "today"
    elif target_date == tomorrow:
        day_label = "tomorrow"
    else:
        day_label = dt.strftime("%A, %B %-d")   # e.g. "Monday, September 1"

    # Time label
    hour = dt.hour
    if hour == 10 and dt.minute == 0:
        time_label = "10am"
    elif hour < 12:
        time_label = f"{hour}am"
    elif hour == 12:
        time_label = "noon"
    elif hour == 14 and dt.minute == 0:
        time_label = "2pm"
    elif hour == 18 and dt.minute == 0:
        time_label = "6pm"
    elif hour == 20 and dt.minute == 0:
        time_label = "8pm"
    else:
        suffix = "am" if hour < 12 else "pm"
        display_hour = hour if hour <= 12 else hour - 12
        time_label = f"{display_hour}{suffix}"

    return f"So around {time_label} {day_label}?"


def book(call_id: str, dt: datetime) -> None:
    """Store a confirmed callback booking for a call."""
    _bookings[call_id] = dt
    logger.info(f"[scheduler] Booked callback for {call_id}: {dt}")


def get_booking(call_id: str) -> Optional[datetime]:
    """Retrieve a stored booking, or None."""
    return _bookings.get(call_id)
