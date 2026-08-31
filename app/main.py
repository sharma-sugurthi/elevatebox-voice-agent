"""
app/main.py — FastAPI server. The heart of ElevateBox.

Endpoints:
  GET  /health              — Heroku uptime check
  POST /chat/completions    — Vapi Custom LLM (OpenAI-compatible format)
  POST /vapi/webhook        — Vapi event stream (end-of-call, status, assistant-request)
  POST /call/trigger        — Starts the outbound call to evaluator (needs paid number)

Design rules:
  - /chat/completions NEVER returns 5xx — Vapi treats that as a broken call.
    On any error, return the fallback "say" text.
  - WhatsApp sends are fire-and-forget (asyncio.create_task) — never block the
    voice response waiting for a WhatsApp HTTP call.
  - All state mutations happen BEFORE returning the voice response so the next
    turn has the updated context.
  - Server starts even without Vapi/WhatsApp keys — brain logic works standalone.
"""

import asyncio
import logging
import uuid
from typing import Optional

import httpx
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import JSONResponse

from app import config
from app import state as state_store
from app import llm, whatsapp, scheduler
from app.prompts import build_system_prompt, OPENING_LINE

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="ElevateBox Voice Agent", version="1.0.0")

# ── Voice config ──────────────────────────────────────────────────────────────
# Azure Neural Indian English voice for "Priya"
VOICE_CONFIG = {
    "provider": "azure",
    "voiceId": "en-IN-NeerjaNeural",
}

# Vapi API base URL
VAPI_API_BASE = "https://api.vapi.ai"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _openai_response(text: str) -> dict:
    """Wrap spoken text in OpenAI chat completion response format."""
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
    }


def _extract_call_id(body: dict) -> str:
    """
    Extract call_id from Vapi Custom LLM request body.
    Vapi sends it in body.call.id. Fall back to a UUID if missing
    (e.g. during local testing with fake payloads).
    """
    try:
        return body["call"]["id"]
    except (KeyError, TypeError):
        fallback = f"local-{uuid.uuid4().hex[:6]}"
        logger.warning(f"[main] call_id not found in body — using fallback: {fallback}")
        return fallback


def _extract_user_messages(messages: list) -> list[dict]:
    """
    Filter the messages array from Vapi to remove system messages.
    Converts assistant messages to have role='assistant', user to 'user'.
    Returns only the conversation turns.
    """
    return [
        {"role": m["role"], "content": m.get("content") or ""}
        for m in messages
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]


def _get_customer_name(st) -> str:
    """Best-effort customer name from state — defaults to 'there'."""
    return "there"   # will improve if we add name detection to LLM output


async def _fire_hot_lead_whatsapp(call_id: str, st) -> None:
    """
    Fire the mid-call hot-lead WhatsApp. Runs as a background task.
    Marks whatsapp_sent=True BEFORE sending to prevent duplicate fires
    (next turn may arrive before send completes).
    """
    st.whatsapp_sent = True   # set flag immediately
    name = _get_customer_name(st)
    sells = st.discovery.sells or "your business"
    success = await whatsapp.send_hot_lead(
        to=config.EVALUATOR_PHONE,
        customer_name=name,
        what_they_sell=sells,
    )
    if not success:
        # Don't reset whatsapp_sent — we tried. Better than spamming on retry.
        logger.error(f"[main] Hot-lead WhatsApp failed for {call_id}")


async def _fire_post_call_whatsapp(call_id: str) -> None:
    """
    Fire the post-call summary WhatsApp. Called on end-of-call-report.
    """
    st = state_store.get(call_id)
    if st is None:
        logger.warning(f"[main] post-call WhatsApp: no state for {call_id}")
        return

    summary = whatsapp.build_call_summary(st)
    name = _get_customer_name(st)

    success = await whatsapp.send_post_call(
        to=config.EVALUATOR_PHONE,
        customer_name=name,
        call_summary=summary,
        developer_phone=config.MY_PHONE,
    )
    if success:
        logger.info(f"[main] Post-call WhatsApp sent for {call_id}")
    else:
        logger.error(f"[main] Post-call WhatsApp failed for {call_id}")

    state_store.clear(call_id)


def _build_assistant_config() -> dict:
    """
    Build the Vapi assistant configuration for inbound/outbound calls.
    This tells Vapi to use our Custom LLM endpoint as the brain.
    """
    return {
        "model": {
            "provider": "custom-llm",
            "url": f"{config.PUBLIC_BASE_URL}/chat/completions",
            "model": "elevatebox-priya",
        },
        "voice": VOICE_CONFIG,
        "firstMessage": OPENING_LINE,
        "serverUrl": f"{config.PUBLIC_BASE_URL}/vapi/webhook",
        "endCallMessage": "Thanks for your time. Speak soon!",
        "backgroundSound": "off",
        "silenceTimeoutSeconds": 30,
        "maxDurationSeconds": 300,   # 5-minute cap
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Heroku uptime check — must return 200."""
    return {
        "status": "ok",
        "service": "elevatebox-voice-agent",
        "whatsapp_enabled": config.WHATSAPP_ENABLED,
        "vapi_enabled": config.VAPI_ENABLED,
    }


@app.post("/chat/completions")
async def chat_completions(request: Request):
    """
    Vapi Custom LLM endpoint (OpenAI-compatible).

    Called by Vapi on EVERY conversation turn. Must respond in < 3s or
    Vapi will time out and dead-air the call. Our LLM module enforces this
    with its own 3s asyncio.wait_for timeout + fallback.

    Request shape (from Vapi):
      {
        "model": "...",
        "messages": [{"role": "user"|"assistant"|"system", "content": "..."}],
        "call": {"id": "call_xxx", ...},
        ...
      }

    Response shape (OpenAI format):
      {
        "id": "chatcmpl-xxx",
        "object": "chat.completion",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "..."},
                     "finish_reason": "stop"}]
      }
    """
    try:
        body = await request.json()
    except Exception:
        logger.error("[/chat/completions] Failed to parse request body")
        return JSONResponse(_openai_response("Sorry, could you repeat that?"))

    call_id = _extract_call_id(body)
    raw_messages = body.get("messages", [])
    messages = _extract_user_messages(raw_messages)

    logger.info(f"[/chat/completions] call={call_id} turns={len(messages)}")

    # No user turns yet — Vapi is initialising, return the opening line
    if not messages:
        return JSONResponse(_openai_response(OPENING_LINE))

    # Get or create call state
    st = state_store.get_or_create(call_id)

    # Build system prompt from current state
    system_prompt = build_system_prompt(st)

    # Append latest user turn to transcript
    latest_user_msg = messages[-1]["content"]
    state_store.append_transcript(call_id, "user", latest_user_msg)

    # Call the LLM brain — NEVER raises (has internal fallback)
    llm_output = await llm.think(system_prompt, messages, st)

    # Update state from LLM output
    state_store.update_from_llm(call_id, llm_output)
    st = state_store.get(call_id)   # refresh reference

    # Handle callback phrase (deterministic — no LLM)
    if llm_output.get("callback_phrase") and st.callback_booked is None:
        dt = scheduler.parse_callback_time(llm_output["callback_phrase"])
        if dt:
            scheduler.book(call_id, dt)
            st.callback_booked = dt
            logger.info(f"[main] Callback booked for {call_id}: {dt}")

    # Fire hot-lead WhatsApp (fire-and-forget — don't block voice response)
    if llm_output.get("fire_whatsapp_now") and not st.whatsapp_sent:
        asyncio.create_task(_fire_hot_lead_whatsapp(call_id, st))

    # Extract spoken response
    spoken = llm_output.get("say") or "Could you say that again?"

    # Append assistant turn to transcript
    state_store.append_transcript(call_id, "assistant", spoken)

    return JSONResponse(_openai_response(spoken))


@app.post("/vapi/webhook")
async def vapi_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Vapi server-URL webhook — receives call lifecycle events.

    Key events we handle:
      assistant-request   → INBOUND calls: return assistant config so Vapi uses our brain
      end-of-call-report  → fire post-call summary WhatsApp, clear state
      status-update       → log only (for now)

    Vapi expects a 200 OK quickly — all heavy work goes to background_tasks.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"status": "ok"})

    msg = body.get("message", {})
    event_type = msg.get("type", "unknown")
    call = msg.get("call", {})
    call_id = call.get("id", "unknown")

    logger.info(f"[/vapi/webhook] event={event_type} call={call_id}")

    # ── INBOUND: Vapi asks "which assistant should handle this call?" ─────
    if event_type == "assistant-request":
        logger.info(f"[/vapi/webhook] Inbound call received — returning Priya assistant config")
        return JSONResponse({"assistant": _build_assistant_config()})

    # ── END OF CALL: fire post-call WhatsApp ──────────────────────────────
    if event_type == "end-of-call-report":
        background_tasks.add_task(_fire_post_call_whatsapp, call_id)

    elif event_type == "status-update":
        status = msg.get("status", "")
        logger.info(f"[/vapi/webhook] status-update: {status} for call {call_id}")

        # If call ended unexpectedly (no end-of-call-report), fire post-call anyway
        if status == "ended":
            st = state_store.get(call_id)
            if st is not None:
                background_tasks.add_task(_fire_post_call_whatsapp, call_id)

    elif event_type == "transcript":
        # Real-time transcript — log only
        role = msg.get("role", "unknown")
        transcript = msg.get("transcript", "")
        logger.debug(f"[transcript] {role}: {transcript[:80]}")

    # Always 200 — Vapi retries on non-200 which can cause duplicate actions
    return JSONResponse({"status": "ok"})


@app.post("/call/trigger")
async def trigger_call(request: Request):
    """
    Trigger an outbound call to the evaluator via Vapi REST API.

    Optional JSON body:
      { "phone": "+918688664337" }   — overrides EVALUATOR_PHONE from .env

    Uses Vapi's Custom LLM mode so our /chat/completions is the brain.
    Requires a paid Vapi/Twilio number (VAPI_ENABLED must be True).
    """
    if not config.VAPI_ENABLED:
        return JSONResponse(
            {
                "status": "error",
                "detail": "Outbound calling disabled — VAPI_API_KEY and VAPI_PHONE_NUMBER_ID not configured. "
                          "Use the inbound Vapi number to test instead.",
            },
            status_code=503,
        )

    try:
        body = await request.json()
        to_phone = body.get("phone", config.EVALUATOR_PHONE)
    except Exception:
        to_phone = config.EVALUATOR_PHONE

    logger.info(f"[/call/trigger] Initiating call to {to_phone}")

    call_payload = {
        "phoneNumberId": config.VAPI_PHONE_NUMBER_ID,
        "customer": {
            "number": to_phone,
        },
        "assistant": _build_assistant_config(),
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{VAPI_API_BASE}/call/phone",
                headers={
                    "Authorization": f"Bearer {config.VAPI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=call_payload,
            )

        if resp.status_code in (200, 201):
            call_data = resp.json()
            call_id = call_data.get("id", "unknown")
            logger.info(f"[/call/trigger] Call started: {call_id}")
            return JSONResponse({
                "status": "call_started",
                "call_id": call_id,
                "to": to_phone,
            })
        else:
            logger.error(f"[/call/trigger] Vapi API error: {resp.status_code} — {resp.text[:300]}")
            return JSONResponse(
                {"status": "error", "detail": resp.text[:300]},
                status_code=resp.status_code,
            )

    except httpx.TimeoutException:
        logger.error("[/call/trigger] Vapi API timed out")
        return JSONResponse({"status": "error", "detail": "Vapi API timeout"}, status_code=504)

    except Exception as e:
        logger.error(f"[/call/trigger] Unexpected error: {e}")
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)
