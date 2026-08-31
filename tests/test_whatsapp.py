"""
tests/test_whatsapp.py — tests for app/whatsapp.py

Two layers:
1. Unit tests (₹0): test payload builder and build_call_summary() with mocked httpx.
2. Live test (uses real WhatsApp API): marked @pytest.mark.live — only run manually
   when you have real keys and templates approved.

Run unit tests only:  pytest tests/test_whatsapp.py -v -m "not live"
Run live test:        pytest tests/test_whatsapp.py -v -m live   (needs real .env)
"""

import asyncio
import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.whatsapp import _build_template_payload, build_call_summary
from app.state import CallState, DiscoveryState, _store


def setup_function():
    _store.clear()


# ── _build_template_payload ───────────────────────────────────────────────────

def test_payload_strips_plus_from_number():
    payload = _build_template_payload(
        to="+918688664337",
        template_name="hot_lead_followup",
        language_code="en_US",
        body_vars=["Ravi", "clothing"],
    )
    assert payload["to"] == "918688664337"


def test_payload_strips_spaces_from_number():
    payload = _build_template_payload(
        to="91 8688 664337",
        template_name="hot_lead_followup",
        language_code="en_US",
        body_vars=["Ravi", "clothing"],
    )
    assert " " not in payload["to"]


def test_payload_messaging_product_is_whatsapp():
    payload = _build_template_payload(
        to="+918688664337",
        template_name="hot_lead_followup",
        language_code="en_US",
        body_vars=["Ravi", "clothing"],
    )
    assert payload["messaging_product"] == "whatsapp"
    assert payload["type"] == "template"


def test_payload_template_name_and_language():
    payload = _build_template_payload(
        to="+918688664337",
        template_name="hot_lead_followup",
        language_code="en_US",
        body_vars=["Ravi", "clothing"],
    )
    assert payload["template"]["name"] == "hot_lead_followup"
    assert payload["template"]["language"]["code"] == "en_US"


def test_payload_body_vars_as_text_parameters():
    payload = _build_template_payload(
        to="+918688664337",
        template_name="hot_lead_followup",
        language_code="en_US",
        body_vars=["Ravi", "clothing"],
    )
    components = payload["template"]["components"]
    body_component = next(c for c in components if c["type"] == "body")
    params = body_component["parameters"]
    assert len(params) == 2
    assert params[0] == {"type": "text", "text": "Ravi"}
    assert params[1] == {"type": "text", "text": "clothing"}


def test_payload_post_call_three_vars():
    payload = _build_template_payload(
        to="+918688664337",
        template_name="post_call_summary",
        language_code="en_US",
        body_vars=["Ravi", "Discussed saree store setup.", "+919876543210"],
    )
    body = payload["template"]["components"][0]
    assert len(body["parameters"]) == 3
    assert body["parameters"][2]["text"] == "+919876543210"


# ── build_call_summary ────────────────────────────────────────────────────────

def test_summary_with_full_discovery():
    state = CallState(call_id="w001")
    state.discovery.sells = "sarees"
    state.discovery.budget = "50,000"
    state.discovery.timeline = "1 month"
    state.discovery.features = ["payment gateway", "catalogue", "COD"]

    summary = build_call_summary(state)
    assert "saree" in summary
    assert "50,000" in summary
    assert "1 month" in summary
    assert "payment gateway" in summary


def test_summary_with_barrier():
    state = CallState(call_id="w002", barrier="budget")
    state.discovery.sells = "clothing"
    summary = build_call_summary(state)
    assert "budget" in summary.lower()


def test_summary_with_callback_booked():
    from datetime import datetime
    state = CallState(call_id="w003")
    state.callback_booked = datetime(2026, 8, 27, 10, 0)
    summary = build_call_summary(state)
    assert "Callback" in summary or "callback" in summary


def test_summary_empty_discovery_returns_default():
    state = CallState(call_id="w004")
    summary = build_call_summary(state)
    assert "e-commerce" in summary.lower() or "website" in summary.lower()


def test_summary_caps_features_at_three():
    state = CallState(call_id="w005")
    state.discovery.features = ["payment", "catalogue", "COD", "WhatsApp", "SMS"]
    summary = build_call_summary(state)
    # Should mention at most 3 features
    feature_count = sum(1 for f in ["payment", "catalogue", "COD", "WhatsApp", "SMS"]
                        if f in summary)
    assert feature_count <= 3


# ── Unit test: _send_template with mocked httpx ───────────────────────────────

@pytest.mark.asyncio
async def test_send_returns_true_on_200():
    """Mock httpx to return 200 — confirm send_hot_lead returns True."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"messages": [{"id": "msg_123"}]}

    with patch("app.whatsapp.config.WHATSAPP_ENABLED", True), \
         patch("app.whatsapp.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        from app.whatsapp import send_hot_lead
        result = await send_hot_lead(
            to="+918688664337",
            customer_name="Ravi",
            what_they_sell="clothing",
        )
        assert result is True


@pytest.mark.asyncio
async def test_send_returns_false_on_400():
    """Mock httpx to return 400 — confirm adapter returns False without raising."""
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = '{"error": "template not approved"}'

    with patch("app.whatsapp.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        from app.whatsapp import send_hot_lead
        result = await send_hot_lead(
            to="+918688664337",
            customer_name="Ravi",
            what_they_sell="clothing",
        )
        assert result is False


# ── Live test (real API — only run manually after templates are approved) ──────

HAS_REAL_WHATSAPP = (
    os.getenv("WHATSAPP_TOKEN", "").startswith("EAA") and
    os.getenv("WHATSAPP_PHONE_NUMBER_ID", "") not in ("", "placeholder", "YOUR_WHATSAPP_PHONE_NUMBER_ID_HERE")
)


@pytest.mark.live
@pytest.mark.skipif(not HAS_REAL_WHATSAPP, reason="Real WhatsApp keys not configured")
def test_live_send_hot_lead_to_own_number():
    """
    Sends a real hot_lead_followup template to MY_PHONE.
    Only run this after templates are approved in Meta dashboard.

    To run: pytest tests/test_whatsapp.py -v -m live
    """
    from app.whatsapp import send_hot_lead
    my_phone = os.getenv("MY_PHONE", "")
    assert my_phone, "MY_PHONE must be set in .env"

    result = asyncio.run(send_hot_lead(
        to=my_phone,
        customer_name="Test",
        what_they_sell="clothing",
    ))
    assert result is True, "Live WhatsApp send failed — check token, phone number ID, and template approval status"
