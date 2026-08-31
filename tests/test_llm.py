"""
tests/test_llm.py — tests for app/llm.py

Two layers:
1. Unit tests (₹0): test _parse_response() and _fallback_response() — no API calls.
2. Integration tests (real Gemini, costs a few free-tier calls): test the full
   think() function with real transcripts. Only runs when GEMINI_API_KEY is set.

Run unit tests only:  pytest tests/test_llm.py -v -m "not integration"
Run all (needs key):  pytest tests/test_llm.py -v
"""

import asyncio
import json
import os
import pytest

from app.state import CallState, DiscoveryState, _store
from app.llm import _parse_response, _fallback_response


def setup_function():
    _store.clear()


# ── Unit tests: _parse_response() ─────────────────────────────────────────────

def test_parse_valid_hot_response():
    raw = json.dumps({
        "say": "Great! Let me tell you about our packages.",
        "language": "en",
        "discovery": {"budget": None, "sells": "clothing", "product_count": None, "timeline": None, "features": []},
        "classification": "hot",
        "confidence": 0.9,
        "barrier": None,
        "callback_phrase": None,
        "fire_whatsapp_now": True,
    })
    result = _parse_response(raw)
    assert result["classification"] == "hot"
    assert result["fire_whatsapp_now"] is True
    assert result["confidence"] == 0.9
    assert result["discovery"]["sells"] == "clothing"


def test_parse_warm_with_barrier():
    raw = json.dumps({
        "say": "Got it, budget's a bit tight. When would be a good time to revisit?",
        "language": "en",
        "discovery": {"budget": "low", "sells": None, "product_count": None, "timeline": None, "features": []},
        "classification": "warm",
        "confidence": 0.8,
        "barrier": "budget",
        "callback_phrase": None,
        "fire_whatsapp_now": False,
    })
    result = _parse_response(raw)
    assert result["classification"] == "warm"
    assert result["barrier"] == "budget"
    assert result["fire_whatsapp_now"] is False


def test_parse_sets_defaults_for_missing_keys():
    """LLM may omit optional keys — _parse_response fills sane defaults."""
    raw = json.dumps({"say": "Hello!"})   # minimal response
    result = _parse_response(raw)
    assert result["language"] == "en"
    assert result["classification"] == "cold"
    assert result["confidence"] == 0.0
    assert result["fire_whatsapp_now"] is False
    assert result["callback_phrase"] is None
    assert result["discovery"]["budget"] is None


def test_parse_clamps_confidence_above_1():
    raw = json.dumps({"say": "Hi", "confidence": 1.5, "classification": "hot"})
    result = _parse_response(raw)
    assert result["confidence"] == 1.0


def test_parse_clamps_confidence_below_0():
    raw = json.dumps({"say": "Hi", "confidence": -0.3, "classification": "cold"})
    result = _parse_response(raw)
    assert result["confidence"] == 0.0


def test_parse_normalises_unknown_classification():
    raw = json.dumps({"say": "Hi", "classification": "maybe"})
    result = _parse_response(raw)
    assert result["classification"] == "cold"


def test_parse_raises_on_invalid_json():
    with pytest.raises(json.JSONDecodeError):
        _parse_response("not json at all")


# ── Unit tests: _fallback_response() ─────────────────────────────────────────

def test_fallback_preserves_current_classification():
    state = CallState(call_id="f001", classification="warm", confidence=0.7, language="hi")
    fb = _fallback_response(state)
    assert fb["say"] == "Sorry, could you say that again?"
    assert fb["classification"] == "warm"
    assert fb["language"] == "hi"
    assert fb["fire_whatsapp_now"] is False


def test_fallback_defaults_language_to_en_when_unknown():
    state = CallState(call_id="f002")
    fb = _fallback_response(state)
    assert fb["language"] == "en"


def test_fallback_never_fires_whatsapp():
    state = CallState(call_id="f003", classification="hot")
    fb = _fallback_response(state)
    assert fb["fire_whatsapp_now"] is False   # NEVER fire on fallback


# ── Integration tests (real Gemini) ───────────────────────────────────────────
# These call the real Gemini API. Only run when GEMINI_API_KEY is a real key.
# Skipped automatically when key is a placeholder.

HAS_REAL_KEY = (
    os.getenv("GEMINI_API_KEY", "").startswith("AI")   # real Gemini keys start with "AI"
)

pytestmark_integration = pytest.mark.skipif(
    not HAS_REAL_KEY,
    reason="GEMINI_API_KEY not set — skipping real Gemini calls"
)


@pytest.mark.integration
@pytestmark_integration
def test_real_gemini_hot_path():
    """
    Feed a hot-intent transcript to the real Gemini API.
    Assert it classifies as hot and sets fire_whatsapp_now=true.
    """
    from app.llm import think
    from app.prompts import build_system_prompt

    state = CallState(call_id="g001")
    messages = [
        {"role": "assistant", "content": "Hi, this is Priya from ElevateBox — is now okay for a quick minute?"},
        {"role": "user", "content": "Yes, how soon can you start? And what would this cost?"},
    ]
    prompt = build_system_prompt(state)
    result = asyncio.run(think(prompt, messages, state))

    assert result["classification"] == "hot", f"Expected hot, got: {result['classification']}"
    assert result["fire_whatsapp_now"] is True, "Expected fire_whatsapp_now=True for hot lead"
    assert result["say"], "say field must not be empty"


@pytest.mark.integration
@pytestmark_integration
def test_real_gemini_warm_budget_barrier():
    """Budget barrier → warm classification."""
    from app.llm import think
    from app.prompts import build_system_prompt

    state = CallState(call_id="g002")
    messages = [
        {"role": "assistant", "content": "Hi, this is Priya from ElevateBox!"},
        {"role": "user", "content": "My budget is not much right now, maybe next month."},
    ]
    prompt = build_system_prompt(state)
    result = asyncio.run(think(prompt, messages, state))

    assert result["classification"] in ("warm", "cold")
    # Most important: budget barrier captured
    if result["classification"] == "warm":
        assert result["barrier"] in ("budget", "timing")


@pytest.mark.integration
@pytestmark_integration
def test_real_gemini_vague_is_warm_not_cold():
    """
    'Send me the details' is WARM, not COLD.
    This is explicitly called out as a scoring differentiator.
    """
    from app.llm import think
    from app.prompts import build_system_prompt

    state = CallState(call_id="g003")
    messages = [
        {"role": "assistant", "content": "Hi, this is Priya from ElevateBox!"},
        {"role": "user", "content": "Send me the details, I'll look at it."},
    ]
    prompt = build_system_prompt(state)
    result = asyncio.run(think(prompt, messages, state))

    assert result["classification"] != "cold", (
        "'Send me the details' must be WARM not COLD — this is a scored differentiator"
    )


@pytest.mark.integration
@pytestmark_integration
def test_real_gemini_callback_phrase_captured():
    """'Call me tomorrow morning' → callback_phrase is not None."""
    from app.llm import think
    from app.prompts import build_system_prompt

    state = CallState(call_id="g004")
    messages = [
        {"role": "assistant", "content": "When would be a good time to call back?"},
        {"role": "user", "content": "Call me tomorrow morning, around 10."},
    ]
    prompt = build_system_prompt(state)
    result = asyncio.run(think(prompt, messages, state))

    assert result["callback_phrase"] is not None, "callback_phrase must be captured"
    assert "tomorrow" in result["callback_phrase"].lower() or "morning" in result["callback_phrase"].lower()


@pytest.mark.integration
@pytestmark_integration
def test_real_gemini_language_detection_telugu():
    """First reply in Telugu → language='te'."""
    from app.llm import think
    from app.prompts import build_system_prompt

    state = CallState(call_id="g005")
    messages = [
        {"role": "assistant", "content": "Hi, this is Priya from ElevateBox!"},
        {"role": "user", "content": "Enti cheppinaru? Website ante ela untundi?"},  # Telugu
    ]
    prompt = build_system_prompt(state)
    result = asyncio.run(think(prompt, messages, state))

    assert result["language"] == "te", f"Expected 'te', got '{result['language']}'"
