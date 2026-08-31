"""
tests/test_state.py — unit tests for app/state.py

Tests run with: pytest tests/test_state.py -v
Cost: ₹0 — no API calls.
"""

import pytest
from app.state import (
    get_or_create, get, update_from_llm, append_transcript,
    clear, CallState, DiscoveryState, _store
)


def setup_function():
    """Clear the in-memory store before each test."""
    _store.clear()


# ── get_or_create ──────────────────────────────────────────────────────────────

def test_creates_new_state_for_unknown_call_id():
    state = get_or_create("call_001")
    assert isinstance(state, CallState)
    assert state.call_id == "call_001"
    assert state.language is None
    assert state.classification == "cold"
    assert state.whatsapp_sent is False


def test_returns_same_state_for_same_call_id():
    s1 = get_or_create("call_001")
    s1.language = "te"
    s2 = get_or_create("call_001")
    assert s2.language == "te"   # same object returned


def test_get_returns_none_for_unknown_id():
    assert get("call_nonexistent") is None


# ── Language lock ──────────────────────────────────────────────────────────────

def test_language_is_locked_after_first_detection():
    update_from_llm("call_002", {"language": "te", "discovery": {}, "classification": "cold", "confidence": 0.3})
    # Second turn tries to change language — must NOT change
    update_from_llm("call_002", {"language": "en", "discovery": {}, "classification": "cold", "confidence": 0.3})
    state = get("call_002")
    assert state.language == "te"   # locked to first detected


def test_language_set_on_first_turn():
    update_from_llm("call_003", {"language": "hi", "discovery": {}, "classification": "cold", "confidence": 0.2})
    assert get("call_003").language == "hi"


# ── Discovery merge ────────────────────────────────────────────────────────────

def test_discovery_fills_null_fields():
    update_from_llm("call_004", {
        "language": "en",
        "discovery": {"budget": "50000", "sells": "sarees", "product_count": None, "timeline": None, "features": []},
        "classification": "warm",
        "confidence": 0.6
    })
    state = get("call_004")
    assert state.discovery.budget == "50000"
    assert state.discovery.sells == "sarees"
    assert state.discovery.product_count is None   # not yet captured


def test_discovery_never_overwrites_captured_value():
    update_from_llm("call_005", {
        "language": "en",
        "discovery": {"budget": "50000", "sells": None, "product_count": None, "timeline": None, "features": []},
        "classification": "cold",
        "confidence": 0.2
    })
    # Second turn tries to change budget — must NOT change
    update_from_llm("call_005", {
        "language": "en",
        "discovery": {"budget": "10000", "sells": "kurtas", "product_count": None, "timeline": None, "features": []},
        "classification": "warm",
        "confidence": 0.5
    })
    state = get("call_005")
    assert state.discovery.budget == "50000"   # original value preserved
    assert state.discovery.sells == "kurtas"   # new value filled in (was null)


def test_missing_fields_returns_correct_list():
    disc = DiscoveryState(budget="50000", sells="sarees")
    missing = disc.missing_fields()
    assert "budget" not in missing
    assert "sells" not in missing
    assert "product_count" in missing
    assert "timeline" in missing
    assert "features" in missing


def test_discovery_complete_when_all_filled():
    disc = DiscoveryState(
        budget="50000",
        sells="sarees",
        product_count="100",
        timeline="1 month",
        features=["payment gateway", "catalogue"]
    )
    assert disc.is_complete() is True


# ── Classification update ──────────────────────────────────────────────────────

def test_classification_updates_each_turn():
    update_from_llm("call_006", {
        "language": "en", "discovery": {},
        "classification": "cold", "confidence": 0.2, "barrier": None
    })
    update_from_llm("call_006", {
        "language": "en", "discovery": {},
        "classification": "hot", "confidence": 0.85, "barrier": None
    })
    state = get("call_006")
    assert state.classification == "hot"
    assert state.confidence == 0.85


def test_barrier_captured():
    update_from_llm("call_007", {
        "language": "en", "discovery": {},
        "classification": "warm", "confidence": 0.7, "barrier": "budget"
    })
    assert get("call_007").barrier == "budget"


# ── Transcript ─────────────────────────────────────────────────────────────────

def test_transcript_appends_in_order():
    append_transcript("call_008", "user", "Hello")
    append_transcript("call_008", "assistant", "Hi, I'm Priya!")
    append_transcript("call_008", "user", "Tell me more.")
    state = get("call_008")
    assert len(state.transcript) == 3
    assert state.transcript[0] == {"role": "user", "content": "Hello"}
    assert state.transcript[1]["role"] == "assistant"


# ── Clear ──────────────────────────────────────────────────────────────────────

def test_clear_removes_state():
    get_or_create("call_009")
    clear("call_009")
    assert get("call_009") is None


def test_clear_nonexistent_does_not_raise():
    clear("call_nonexistent")   # should not raise
