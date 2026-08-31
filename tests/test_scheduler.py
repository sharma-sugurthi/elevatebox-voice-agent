"""
tests/test_scheduler.py — unit tests for app/scheduler.py

All tests are deterministic Python — no API calls, cost ₹0.
We pin 'now' to a fixed datetime so results are predictable.

Run: pytest tests/test_scheduler.py -v
"""

from datetime import datetime, time
import pytest

from app.scheduler import (
    parse_callback_time,
    format_confirmation,
    book,
    get_booking,
    _bookings,
)


# Fixed "now" used across tests: Tuesday 2026-08-26 at 15:00 IST
NOW = datetime(2026, 8, 26, 15, 0, 0)


def setup_function():
    _bookings.clear()


# ── parse_callback_time ────────────────────────────────────────────────────────

def test_tomorrow_morning():
    result = parse_callback_time("call me tomorrow morning", now=NOW)
    assert result is not None
    assert result.date() == datetime(2026, 8, 27).date()
    assert result.hour == 10
    assert result.minute == 0


def test_tomorrow_evening():
    result = parse_callback_time("tomorrow evening", now=NOW)
    assert result.date() == datetime(2026, 8, 27).date()
    assert result.hour == 18


def test_after_lunch():
    result = parse_callback_time("call me after lunch", now=NOW)
    # "after lunch" with no day → defaults to tomorrow (today at 14:00 is in the past relative to 15:00)
    assert result is not None
    assert result.hour == 14


def test_tomorrow_after_lunch():
    result = parse_callback_time("tomorrow after lunch", now=NOW)
    assert result.date() == datetime(2026, 8, 27).date()
    assert result.hour == 14


def test_evening():
    result = parse_callback_time("evening sometime", now=NOW)
    assert result is not None
    assert result.hour == 18


def test_night():
    result = parse_callback_time("call me tonight", now=NOW)
    assert result is not None
    assert result.hour == 20


def test_next_week():
    result = parse_callback_time("next week", now=NOW)
    assert result is not None
    # next week Monday from Tuesday 26 Aug = Monday 31 Aug
    assert result.date() == datetime(2026, 8, 31).date()
    assert result.hour == 10


def test_day_after_tomorrow():
    result = parse_callback_time("day after tomorrow", now=NOW)
    assert result is not None
    assert result.date() == datetime(2026, 8, 28).date()


def test_no_time_keyword_defaults_to_tomorrow_10am():
    # Just a vague phrase with no time-of-day keyword
    result = parse_callback_time("call me later", now=NOW)
    assert result is not None
    assert result.hour == 10   # defaults to 10am


def test_none_phrase_returns_none():
    result = parse_callback_time(None, now=NOW)
    assert result is None


def test_empty_phrase_returns_none():
    result = parse_callback_time("", now=NOW)
    assert result is None


def test_morning_early_in_day_stays_today():
    """If 'this morning' is said at 7am, we interpret as today at 10am."""
    early = datetime(2026, 8, 26, 7, 0, 0)
    result = parse_callback_time("this morning", now=early)
    # today=0 offset, morning=10am — 10am hasn't passed yet at 7am
    assert result.date() == early.date()
    assert result.hour == 10


# ── format_confirmation ────────────────────────────────────────────────────────

def test_confirmation_tomorrow_morning():
    dt = datetime(2026, 8, 27, 10, 0)
    result = format_confirmation(dt, now=NOW)
    assert "10am" in result
    assert "tomorrow" in result
    assert result.endswith("?")


def test_confirmation_tomorrow_2pm():
    dt = datetime(2026, 8, 27, 14, 0)
    result = format_confirmation(dt, now=NOW)
    assert "2pm" in result
    assert "tomorrow" in result


def test_confirmation_today():
    dt = datetime(2026, 8, 26, 18, 0)
    result = format_confirmation(dt, now=NOW)
    assert "today" in result
    assert "6pm" in result


def test_confirmation_future_date():
    dt = datetime(2026, 9, 1, 10, 0)
    result = format_confirmation(dt, now=NOW)
    # Not today or tomorrow — should show day name
    assert "10am" in result
    assert "today" not in result
    assert "tomorrow" not in result


# ── booking store ─────────────────────────────────────────────────────────────

def test_book_and_retrieve():
    dt = datetime(2026, 8, 27, 10, 0)
    book("call_001", dt)
    assert get_booking("call_001") == dt


def test_get_booking_returns_none_for_unknown_call():
    assert get_booking("call_unknown") is None


def test_book_overwrites_previous():
    dt1 = datetime(2026, 8, 27, 10, 0)
    dt2 = datetime(2026, 8, 28, 14, 0)
    book("call_002", dt1)
    book("call_002", dt2)
    assert get_booking("call_002") == dt2


# ── end-to-end: parse → format ────────────────────────────────────────────────

def test_full_flow_tomorrow_morning():
    """Simulate the full callback flow: phrase → datetime → confirmation string."""
    phrase = "call me tomorrow morning"
    dt = parse_callback_time(phrase, now=NOW)
    confirmation = format_confirmation(dt, now=NOW)
    assert "10am" in confirmation
    assert "tomorrow" in confirmation
    assert "?" in confirmation


def test_full_flow_after_lunch():
    phrase = "after lunch sometime"
    dt = parse_callback_time(phrase, now=NOW)
    confirmation = format_confirmation(dt, now=NOW)
    assert "2pm" in confirmation
    assert "?" in confirmation
