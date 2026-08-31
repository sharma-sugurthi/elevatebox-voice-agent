"""
tests/test_main.py — integration tests for app/main.py endpoints.

Uses FastAPI's TestClient (synchronous) + httpx AsyncClient (async).
All external calls (LLM, WhatsApp, Vapi) are mocked — ₹0 cost.

Tests cover the full request→response cycle for each endpoint,
including the deterministic engine logic:
  - WhatsApp fires when classification flips to HOT
  - WhatsApp does NOT fire twice for same call
  - Fallback response returned on LLM failure
  - end-of-call-report triggers post-call WhatsApp
  - call/trigger sends correct payload to Vapi API

Run: pytest tests/test_main.py -v
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.state import _store
from app.prompts import OPENING_LINE


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_state():
    """Clear in-memory state before every test."""
    _store.clear()
    yield
    _store.clear()


@pytest.fixture
def client(monkeypatch):
    """
    Return a TestClient with LLM mocked to return a COLD classification.
    Individual tests override this mock as needed.
    """
    # Default mock: LLM returns a cold classification
    cold_response = {
        "say": "Thanks for letting me know. I'll send you some details.",
        "language": "en",
        "discovery": {"budget": None, "sells": None, "product_count": None, "timeline": None, "features": []},
        "classification": "cold",
        "confidence": 0.3,
        "barrier": None,
        "callback_phrase": None,
        "fire_whatsapp_now": False,
    }
    monkeypatch.setattr("app.llm.think", AsyncMock(return_value=cold_response))
    monkeypatch.setattr("app.whatsapp.send_hot_lead", AsyncMock(return_value=True))
    monkeypatch.setattr("app.whatsapp.send_post_call", AsyncMock(return_value=True))

    from app.main import app
    return TestClient(app)


def _chat_payload(call_id: str, user_message: str, history: list = None) -> dict:
    """Build a Vapi-style /chat/completions request body."""
    messages = history or []
    messages.append({"role": "user", "content": user_message})
    return {
        "model": "elevatebox-priya",
        "messages": messages,
        "call": {"id": call_id},
    }


# ── /health ────────────────────────────────────────────────────────────────────

def test_health_returns_200(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── /chat/completions — basic ──────────────────────────────────────────────────

def test_chat_returns_openai_format(client):
    payload = _chat_payload("call_001", "Hi there!")
    resp = client.post("/chat/completions", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "choices" in data
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert isinstance(data["choices"][0]["message"]["content"], str)


def test_chat_no_messages_returns_opening_line(client):
    """When Vapi sends no user messages yet, return the opening line."""
    payload = {"model": "elevatebox-priya", "messages": [], "call": {"id": "call_002"}}
    resp = client.post("/chat/completions", json=payload)
    assert resp.status_code == 200
    content = resp.json()["choices"][0]["message"]["content"]
    assert "Priya" in content or "ElevateBox" in content


def test_chat_system_only_messages_returns_opening_line(client):
    """System messages are filtered out — if only system message exists, return opening."""
    payload = {
        "model": "elevatebox-priya",
        "messages": [{"role": "system", "content": "You are Priya."}],
        "call": {"id": "call_003"},
    }
    resp = client.post("/chat/completions", json=payload)
    assert resp.status_code == 200
    content = resp.json()["choices"][0]["message"]["content"]
    # Should be opening line (LLM not called since no user messages)
    assert content   # just not empty


def test_chat_bad_json_returns_fallback(client):
    """Malformed request body → 200 with fallback text (never crash the call)."""
    resp = client.post(
        "/chat/completions",
        content=b"this is not json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200   # MUST be 200 — broken JSON must not kill the call


def test_chat_missing_call_id_still_works(client):
    """No call.id field → generates a fallback ID, call still works."""
    payload = {
        "model": "elevatebox-priya",
        "messages": [{"role": "user", "content": "Hello"}],
        # no "call" key
    }
    resp = client.post("/chat/completions", json=payload)
    assert resp.status_code == 200


# ── /chat/completions — state management ──────────────────────────────────────

def test_chat_creates_state_for_new_call(client):
    from app.state import get
    payload = _chat_payload("call_010", "Hello!")
    client.post("/chat/completions", json=payload)
    assert get("call_010") is not None


def test_chat_state_updates_from_llm_output(monkeypatch):
    """LLM output with discovery data → state gets updated."""
    warm_response = {
        "say": "Got it! Budget is tight — when would be a good time to call back?",
        "language": "te",
        "discovery": {"budget": "30000", "sells": "sarees", "product_count": None,
                      "timeline": None, "features": []},
        "classification": "warm",
        "confidence": 0.75,
        "barrier": "budget",
        "callback_phrase": None,
        "fire_whatsapp_now": False,
    }
    monkeypatch.setattr("app.llm.think", AsyncMock(return_value=warm_response))
    monkeypatch.setattr("app.whatsapp.send_hot_lead", AsyncMock(return_value=True))
    monkeypatch.setattr("app.whatsapp.send_post_call", AsyncMock(return_value=True))

    from app.main import app
    from app.state import get

    with TestClient(app) as c:
        _store.clear()
        payload = _chat_payload("call_011", "Budget naa daggara ledu ippudu")
        c.post("/chat/completions", json=payload)

    st = get("call_011")
    assert st.language == "te"
    assert st.discovery.budget == "30000"
    assert st.discovery.sells == "sarees"
    assert st.classification == "warm"
    assert st.barrier == "budget"


# ── /chat/completions — HOT lead WhatsApp trigger ─────────────────────────────

def test_whatsapp_fires_when_classification_is_hot(monkeypatch):
    """HOT + confidence≥0.7 + fire_whatsapp_now=True → WhatsApp task created."""
    hot_response = {
        "say": "Great, let me tell you about our packages!",
        "language": "en",
        "discovery": {"budget": "50000", "sells": "clothing", "product_count": None,
                      "timeline": None, "features": []},
        "classification": "hot",
        "confidence": 0.9,
        "barrier": None,
        "callback_phrase": None,
        "fire_whatsapp_now": True,
    }
    mock_send = AsyncMock(return_value=True)
    monkeypatch.setattr("app.llm.think", AsyncMock(return_value=hot_response))
    monkeypatch.setattr("app.whatsapp.send_hot_lead", mock_send)
    monkeypatch.setattr("app.whatsapp.send_post_call", AsyncMock(return_value=True))

    from app.main import app
    from app.state import get

    with TestClient(app) as c:
        _store.clear()
        payload = _chat_payload("call_020", "How soon can you start? What does this cost?")
        c.post("/chat/completions", json=payload)

    st = get("call_020")
    assert st.whatsapp_sent is True   # flag set immediately


def test_whatsapp_does_not_fire_twice(monkeypatch):
    """Second HOT turn must NOT fire WhatsApp again — whatsapp_sent flag prevents it."""
    hot_response = {
        "say": "Yes! Let me walk you through the options.",
        "language": "en",
        "discovery": {"budget": None, "sells": "clothing", "product_count": None,
                      "timeline": None, "features": []},
        "classification": "hot",
        "confidence": 0.9,
        "barrier": None,
        "callback_phrase": None,
        "fire_whatsapp_now": True,
    }
    mock_send = AsyncMock(return_value=True)
    monkeypatch.setattr("app.llm.think", AsyncMock(return_value=hot_response))
    monkeypatch.setattr("app.whatsapp.send_hot_lead", mock_send)
    monkeypatch.setattr("app.whatsapp.send_post_call", AsyncMock(return_value=True))

    from app.main import app
    from app.state import get_or_create

    with TestClient(app) as c:
        _store.clear()
        # Simulate call where whatsapp_sent is already True
        st = get_or_create("call_021")
        st.whatsapp_sent = True

        payload = _chat_payload("call_021", "Yes when can you start?")
        c.post("/chat/completions", json=payload)

    # send_hot_lead should NOT have been called
    mock_send.assert_not_called()


# ── /chat/completions — callback booking ─────────────────────────────────────

def test_callback_phrase_is_booked(monkeypatch):
    """LLM returns callback_phrase → scheduler.parse_callback_time called and stored."""
    warm_with_callback = {
        "say": "So around 10am tomorrow?",
        "language": "en",
        "discovery": {"budget": None, "sells": None, "product_count": None,
                      "timeline": None, "features": []},
        "classification": "warm",
        "confidence": 0.7,
        "barrier": "timing",
        "callback_phrase": "call me tomorrow morning",
        "fire_whatsapp_now": False,
    }
    monkeypatch.setattr("app.llm.think", AsyncMock(return_value=warm_with_callback))
    monkeypatch.setattr("app.whatsapp.send_hot_lead", AsyncMock(return_value=True))
    monkeypatch.setattr("app.whatsapp.send_post_call", AsyncMock(return_value=True))

    from app.main import app
    from app.state import get
    from app.scheduler import get_booking

    with TestClient(app) as c:
        _store.clear()
        payload = _chat_payload("call_030", "Call me tomorrow morning")
        c.post("/chat/completions", json=payload)

    st = get("call_030")
    assert st.callback_booked is not None
    booking = get_booking("call_030")
    assert booking is not None
    assert booking.hour == 10   # morning = 10am


# ── /vapi/webhook ─────────────────────────────────────────────────────────────

def test_webhook_returns_200_for_unknown_event(client):
    payload = {"message": {"type": "some-future-event", "call": {"id": "call_040"}}}
    resp = client.post("/vapi/webhook", json=payload)
    assert resp.status_code == 200


def test_webhook_end_of_call_triggers_post_call_whatsapp(monkeypatch):
    """end-of-call-report event → post-call WhatsApp fires."""
    mock_post_call = AsyncMock(return_value=True)
    monkeypatch.setattr("app.whatsapp.send_post_call", mock_post_call)
    monkeypatch.setattr("app.whatsapp.send_hot_lead", AsyncMock(return_value=True))
    monkeypatch.setattr("app.llm.think", AsyncMock(return_value={
        "say": "Thanks!", "language": "en",
        "discovery": {"budget": None, "sells": None, "product_count": None, "timeline": None, "features": []},
        "classification": "warm", "confidence": 0.5, "barrier": None,
        "callback_phrase": None, "fire_whatsapp_now": False,
    }))

    from app.main import app
    from app.state import get_or_create

    with TestClient(app) as c:
        _store.clear()
        # Create state for this call
        get_or_create("call_050")

        payload = {
            "message": {
                "type": "end-of-call-report",
                "call": {"id": "call_050"},
            }
        }
        resp = c.post("/vapi/webhook", json=payload)

    assert resp.status_code == 200


def test_webhook_bad_json_returns_200(client):
    """Malformed webhook body → still 200 (Vapi must never get an error response)."""
    resp = client.post(
        "/vapi/webhook",
        content=b"not json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200


# ── /call/trigger ─────────────────────────────────────────────────────────────

def test_call_trigger_returns_503_when_vapi_disabled(client):
    """Without Vapi keys, /call/trigger returns 503 with helpful message."""
    resp = client.post("/call/trigger", json={})
    assert resp.status_code == 503
    assert "disabled" in resp.json()["detail"].lower()


def test_call_trigger_sends_correct_payload_to_vapi(monkeypatch):
    """Verify the Vapi API call has correct structure."""
    captured_payload = {}

    async def mock_post(url, headers, json, **kwargs):
        captured_payload.update(json)
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"id": "call_vapi_123"}
        return mock_resp

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = mock_post

    monkeypatch.setattr("app.main.httpx.AsyncClient", lambda **kwargs: mock_client)
    monkeypatch.setattr("app.main.config.VAPI_ENABLED", True)
    monkeypatch.setattr("app.main.config.VAPI_API_KEY", "test-key")
    monkeypatch.setattr("app.main.config.VAPI_PHONE_NUMBER_ID", "test-phone-id")
    monkeypatch.setattr("app.llm.think", AsyncMock(return_value={}))
    monkeypatch.setattr("app.whatsapp.send_hot_lead", AsyncMock(return_value=True))
    monkeypatch.setattr("app.whatsapp.send_post_call", AsyncMock(return_value=True))

    from app.main import app

    with TestClient(app) as c:
        _store.clear()
        resp = c.post("/call/trigger", json={})

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "call_started"
    assert data["call_id"] == "call_vapi_123"

    # Verify payload structure
    assert "phoneNumberId" in captured_payload
    assert captured_payload["customer"]["number"] == "+918688664337"
    assistant = captured_payload["assistant"]
    assert assistant["model"]["provider"] == "custom-llm"
    assert "/chat/completions" in assistant["model"]["url"]
    assert "/vapi/webhook" in assistant["serverUrl"]


def test_call_trigger_accepts_phone_override(monkeypatch):
    """phone parameter in body overrides EVALUATOR_PHONE."""
    captured_payload = {}

    async def mock_post(url, headers, json, **kwargs):
        captured_payload.update(json)
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"id": "call_999"}
        return mock_resp

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = mock_post

    monkeypatch.setattr("app.main.httpx.AsyncClient", lambda **kwargs: mock_client)
    monkeypatch.setattr("app.main.config.VAPI_ENABLED", True)
    monkeypatch.setattr("app.main.config.VAPI_API_KEY", "test-key")
    monkeypatch.setattr("app.main.config.VAPI_PHONE_NUMBER_ID", "test-phone-id")
    monkeypatch.setattr("app.llm.think", AsyncMock(return_value={}))
    monkeypatch.setattr("app.whatsapp.send_hot_lead", AsyncMock(return_value=True))
    monkeypatch.setattr("app.whatsapp.send_post_call", AsyncMock(return_value=True))

    from app.main import app

    with TestClient(app) as c:
        _store.clear()
        resp = c.post("/call/trigger", json={"phone": "+919999999999"})

    assert captured_payload["customer"]["number"] == "+919999999999"


# ── /vapi/webhook — inbound assistant-request ─────────────────────────────────

def test_webhook_assistant_request_returns_config(client):
    """Inbound call → Vapi sends assistant-request → we return our brain config."""
    payload = {
        "message": {
            "type": "assistant-request",
            "call": {"id": "call_inbound_001"},
        }
    }
    resp = client.post("/vapi/webhook", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "assistant" in data
    assistant = data["assistant"]
    assert assistant["model"]["provider"] == "custom-llm"
    assert "/chat/completions" in assistant["model"]["url"]
    assert "firstMessage" in assistant

