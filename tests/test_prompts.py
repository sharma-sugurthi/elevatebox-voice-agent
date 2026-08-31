"""
tests/test_prompts.py — unit tests for app/prompts.py

Tests that build_system_prompt() produces the right content
based on call state. Zero API calls. Cost: ₹0.

Run: pytest tests/test_prompts.py -v
"""

import pytest
from app.state import CallState, DiscoveryState, _store
from app.prompts import build_system_prompt, OPENING_LINE


def setup_function():
    _store.clear()


# ── Language instruction ──────────────────────────────────────────────────────

def test_prompt_has_detect_instruction_when_language_unknown():
    state = CallState(call_id="p001")
    prompt = build_system_prompt(state)
    assert "Detect the language" in prompt


def test_prompt_locks_to_telugu():
    state = CallState(call_id="p002", language="te")
    prompt = build_system_prompt(state)
    assert "LOCKED to Telugu" in prompt
    assert "Detect" not in prompt


def test_prompt_locks_to_hindi():
    state = CallState(call_id="p003", language="hi")
    prompt = build_system_prompt(state)
    assert "LOCKED to Hindi" in prompt


def test_prompt_locks_to_english():
    state = CallState(call_id="p004", language="en")
    prompt = build_system_prompt(state)
    assert "LOCKED to English" in prompt


# ── Discovery gaps ────────────────────────────────────────────────────────────

def test_prompt_lists_all_missing_fields_on_fresh_call():
    state = CallState(call_id="p005")
    prompt = build_system_prompt(state)
    # All 5 fields should be listed as missing
    assert "budget" in prompt
    assert "sells" in prompt
    assert "product_count" in prompt
    assert "timeline" in prompt
    assert "features" in prompt


def test_prompt_excludes_captured_fields():
    state = CallState(call_id="p006")
    state.discovery.budget = "50000"
    state.discovery.sells = "sarees"
    prompt = build_system_prompt(state)
    # Captured fields should NOT appear in missing list
    missing_section = prompt.split("Discovery fields still needed:")[1].split("\n")[0]
    assert "budget" not in missing_section
    assert "sells" not in missing_section
    assert "product_count" in missing_section


def test_prompt_says_focus_on_closing_when_all_filled():
    state = CallState(call_id="p007")
    state.discovery.budget = "50000"
    state.discovery.sells = "sarees"
    state.discovery.product_count = "200"
    state.discovery.timeline = "1 month"
    state.discovery.features = ["payment gateway"]
    prompt = build_system_prompt(state)
    assert "Focus on selling and closing" in prompt


# ── WhatsApp flag ─────────────────────────────────────────────────────────────

def test_prompt_says_not_sent_when_whatsapp_not_sent():
    state = CallState(call_id="p008", whatsapp_sent=False)
    prompt = build_system_prompt(state)
    assert "not yet sent" in prompt


def test_prompt_says_already_sent_when_whatsapp_sent():
    state = CallState(call_id="p009", whatsapp_sent=True)
    prompt = build_system_prompt(state)
    assert "already been sent" in prompt
    assert "do NOT set fire_whatsapp_now=true again" in prompt


# ── Classification context ────────────────────────────────────────────────────

def test_prompt_contains_current_classification():
    state = CallState(call_id="p010", classification="warm", confidence=0.75)
    prompt = build_system_prompt(state)
    assert "warm" in prompt
    assert "75%" in prompt


# ── Output schema ─────────────────────────────────────────────────────────────

def test_prompt_contains_output_schema_keys():
    state = CallState(call_id="p011")
    prompt = build_system_prompt(state)
    assert "fire_whatsapp_now" in prompt
    assert "callback_phrase" in prompt
    assert "classification" in prompt
    assert "Return ONLY the JSON object" in prompt


# ── Opening line ──────────────────────────────────────────────────────────────

def test_opening_line_mentions_elevate_box():
    assert "ElevateBox" in OPENING_LINE
    assert "Priya" in OPENING_LINE
    assert "Hyderabad" in OPENING_LINE
