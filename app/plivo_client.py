"""
app/plivo_client.py — Plivo REST API client for outbound call triggering.

Plivo's outbound call API: POST https://api.plivo.com/v1/Account/{AUTH_ID}/Call/
Docs: https://www.plivo.com/docs/voice/api/call/make-a-call/

Why no Plivo SDK: we already have httpx. Adding plivo-python adds a dep
for three lines of HTTP. Not worth it.
"""

import httpx
import logging
from app import config

logger = logging.getLogger(__name__)

PLIVO_API_BASE = "https://api.plivo.com/v1"


async def trigger_outbound_call(to_number: str, answer_url: str) -> dict:
    """
    Initiate an outbound call from our Plivo US number to `to_number`.

    answer_url: the URL Plivo fetches when the call is picked up.
    For Vapi routing, this should be a Vapi SIP endpoint or an XML response
    that bridges to Vapi. Simplest path: use Vapi's /call/phone endpoint
    to create the outbound call using the Plivo-imported number.

    Returns: Plivo API response dict or raises on failure.
    """
    if not config.PLIVO_ENABLED:
        raise RuntimeError("Plivo not configured — PLIVO_AUTH_ID/TOKEN/FROM_NUMBER missing")

    payload = {
        "from": config.PLIVO_FROM_NUMBER,
        "to": to_number,
        "answer_url": answer_url,
        "answer_method": "GET",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{PLIVO_API_BASE}/Account/{config.PLIVO_AUTH_ID}/Call/",
            auth=(config.PLIVO_AUTH_ID, config.PLIVO_AUTH_TOKEN),
            json=payload,
        )

    resp.raise_for_status()
    return resp.json()
