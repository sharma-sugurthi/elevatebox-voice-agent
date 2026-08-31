"""
app/whatsapp.py — WhatsApp Cloud API adapter.

Two public functions:
  send_hot_lead(to, context_vars)    — mid-call template (fires on HOT classification)
  send_post_call(to, context_vars)   — post-call summary (fires on end-of-call)

Design rules:
- Always async (httpx AsyncClient) — never blocks the voice loop.
- Returns bool (True=success, False=failed) — never raises.
- Retries once on failure, then logs and moves on.
- Uses pre-approved Message Templates only (cold outbound requires this).
- Gracefully disabled when WhatsApp keys are not configured.
"""

import logging
from typing import Optional

import httpx

from app import config

logger = logging.getLogger(__name__)


def _get_api_url() -> str:
    """Build WhatsApp API URL at call time (not import time)."""
    return (
        f"https://graph.facebook.com/v21.0"
        f"/{config.WHATSAPP_PHONE_NUMBER_ID}/messages"
    )


def _get_headers() -> dict:
    """Build auth headers at call time (not import time)."""
    return {
        "Authorization": f"Bearer {config.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }


def _build_template_payload(
    to: str,
    template_name: str,
    language_code: str,
    body_vars: list[str],
) -> dict:
    """
    Build the Meta WhatsApp API payload for a template message.

    to: phone number with country code, no '+', no spaces (e.g. '918688664337')
    body_vars: list of strings for {{1}}, {{2}}, ... in the template body
    """
    # Strip leading '+' and spaces — Meta API expects digits only
    to_clean = to.replace("+", "").replace(" ", "")

    parameters = [
        {"type": "text", "text": var}
        for var in body_vars
    ]

    return {
        "messaging_product": "whatsapp",
        "to": to_clean,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
            "components": [
                {
                    "type": "body",
                    "parameters": parameters,
                }
            ],
        },
    }


async def _send_template(
    to: str,
    template_name: str,
    body_vars: list[str],
    language_code: str = "en_US",
    attempt: int = 1,
) -> bool:
    """
    Internal: POST a template message to the Meta WhatsApp Cloud API.
    Retries once on failure. Returns True on success.
    Returns False immediately if WhatsApp is not configured.
    """
    if not config.WHATSAPP_ENABLED:
        logger.warning(f"[whatsapp] DISABLED — '{template_name}' not sent (keys not configured)")
        return False

    payload = _build_template_payload(to, template_name, language_code, body_vars)

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                _get_api_url(),
                headers=_get_headers(),
                json=payload,
            )

        if resp.status_code == 200:
            logger.info(
                f"[whatsapp] Sent '{template_name}' to {to} — "
                f"message_id={resp.json().get('messages', [{}])[0].get('id', 'unknown')}"
            )
            return True

        # Non-200: log the error, maybe retry
        logger.error(
            f"[whatsapp] '{template_name}' failed (attempt {attempt}): "
            f"HTTP {resp.status_code} — {resp.text[:200]}"
        )

        if attempt == 1:
            import asyncio
            await asyncio.sleep(2)
            return await _send_template(to, template_name, body_vars, language_code, attempt=2)

        return False

    except httpx.TimeoutException:
        logger.error(f"[whatsapp] '{template_name}' timed out (attempt {attempt})")
        if attempt == 1:
            import asyncio
            await asyncio.sleep(2)
            return await _send_template(to, template_name, body_vars, language_code, attempt=2)
        return False

    except Exception as e:
        logger.error(f"[whatsapp] '{template_name}' unexpected error: {e}")
        return False


# ── Public interface ───────────────────────────────────────────────────────────

async def send_hot_lead(
    to: str,
    customer_name: str,
    what_they_sell: str,
) -> bool:
    """
    Send the mid-call hot-lead template.
    Fires the INSTANT classification flips to HOT — while still on the call.

    Template: hot_lead_followup
    Variables: {{1}} = customer name, {{2}} = what they sell
    """
    logger.info(f"[whatsapp] Sending hot_lead to {to}")
    return await _send_template(
        to=to,
        template_name=config.WHATSAPP_HOTLEAD_TEMPLATE,
        body_vars=[customer_name, what_they_sell],
    )


async def send_post_call(
    to: str,
    customer_name: str,
    call_summary: str,
    developer_phone: str,
) -> bool:
    """
    Send the post-call summary template.
    Fires on end-of-call-report event.

    Template: post_call_summary
    Variables: {{1}} = name, {{2}} = summary, {{3}} = developer phone
    """
    logger.info(f"[whatsapp] Sending post_call_summary to {to}")
    return await _send_template(
        to=to,
        template_name=config.WHATSAPP_POSTCALL_TEMPLATE,
        body_vars=[customer_name, call_summary, developer_phone],
    )


def build_call_summary(state) -> str:
    """
    Build a human-readable call summary string from call state.
    Used as {{2}} in the post_call_summary template.
    """
    parts = []

    disc = state.discovery
    if disc.sells:
        parts.append(f"You run a {disc.sells} business")
    if disc.budget:
        parts.append(f"budget around {disc.budget}")
    if disc.timeline:
        parts.append(f"timeline: {disc.timeline}")
    if disc.features:
        features_str = ", ".join(disc.features[:3])  # cap at 3 to keep it short
        parts.append(f"features needed: {features_str}")
    if state.barrier:
        barrier_map = {
            "budget": "You mentioned budget is a constraint right now",
            "timing": "Timing wasn't right today",
            "not_decision_maker": "You mentioned someone else handles these decisions",
        }
        if state.barrier in barrier_map:
            parts.append(barrier_map[state.barrier])
    if state.callback_booked:
        parts.append(
            f"Callback confirmed for {state.callback_booked.strftime('%B %-d at %-I%p IST')}"
        )

    if not parts:
        return "We discussed your e-commerce website needs."

    return ". ".join(parts) + "."
