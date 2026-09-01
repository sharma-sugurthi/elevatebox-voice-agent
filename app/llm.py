"""
app/llm.py — LLM adapter (the swappable brain).

Single public function: think(system_prompt, messages, state) -> dict

Design rules:
- ONE Gemini call per turn. Returns everything: say + classification + discovery + actions.
- 3-second hard timeout. If it fires, return safe fallback so the call never dead-airs.
- All LLM access goes through this module. Swap provider by changing LLM_PROVIDER in .env.
- The adapter is async because FastAPI is async and we must not block the event loop.
"""

import asyncio
import json
import logging

from google import genai
from google.genai import types

from app import config
from app.state import CallState

logger = logging.getLogger(__name__)

# ── Gemini client setup ────────────────────────────────────────────────────────
GEMINI_MODEL = "gemini-3.6-flash"

_gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)

# ── Response schema ────────────────────────────────────────────────────────────
# Default fallback returned when LLM times out or fails.
# Keeps the call alive — Vapi will speak this line.
def _fallback_response(state: CallState) -> dict:
    return {
        "say": "Sorry, could you say that again?",
        "language": state.language or "en",
        "discovery": {
            "budget": state.discovery.budget,
            "sells": state.discovery.sells,
            "product_count": state.discovery.product_count,
            "timeline": state.discovery.timeline,
            "features": state.discovery.features,
        },
        "classification": state.classification,
        "confidence": state.confidence,
        "barrier": state.barrier,
        "callback_phrase": None,
        "fire_whatsapp_now": False,
    }


def _parse_response(raw_text: str) -> dict:
    """
    Parse Gemini's JSON response text into a dict.
    Validates required keys exist. Raises ValueError on bad output.
    """
    data = json.loads(raw_text)

    # Ensure required keys exist with sane defaults
    data.setdefault("say", "Could you repeat that?")
    data.setdefault("language", "en")
    data.setdefault("discovery", {})
    data.setdefault("classification", "cold")
    data.setdefault("confidence", 0.0)
    data.setdefault("barrier", None)
    data.setdefault("callback_phrase", None)
    data.setdefault("fire_whatsapp_now", False)

    # Ensure discovery sub-keys exist
    disc = data["discovery"]
    disc.setdefault("budget", None)
    disc.setdefault("sells", None)
    disc.setdefault("product_count", None)
    disc.setdefault("timeline", None)
    disc.setdefault("features", [])

    # Clamp confidence to [0.0, 1.0]
    data["confidence"] = max(0.0, min(1.0, float(data["confidence"])))

    # Normalise classification
    if data["classification"] not in ("hot", "warm", "cold"):
        data["classification"] = "cold"

    return data


async def _call_gemini(system_prompt: str, messages: list[dict]) -> str:
    """
    Make one async Gemini call.
    messages: list of {"role": "user"|"assistant", "content": str}
    Returns raw JSON string.
    """
    # Build contents list for Gemini (user/model turns)
    contents = []
    for msg in messages:
        gemini_role = "user" if msg["role"] == "user" else "model"
        contents.append(
            types.Content(
                role=gemini_role,
                parts=[types.Part(text=msg["content"])],
            )
        )

    config_obj = types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json",
        temperature=0.3,
        max_output_tokens=512,
    )

    response = await _gemini_client.aio.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=config_obj,
    )
    return response.text


async def _call_groq(system_prompt: str, messages: list[dict]) -> str:
    """
    Groq fallback (Llama 3.3 70B). Wired but not primary.
    Uses httpx to call Groq's OpenAI-compatible endpoint.
    """
    import httpx

    if not config.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set — cannot use Groq fallback")

    groq_messages = [{"role": "system", "content": system_prompt}] + [
        {"role": m["role"], "content": m["content"]} for m in messages
    ]

    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {config.GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "openai/gpt-oss-120b",
                "messages": groq_messages,
                "response_format": {"type": "json_object"},
                "temperature": 0.3,
                "max_tokens": 512,
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


# ── Public interface ───────────────────────────────────────────────────────────

async def think(
    system_prompt: str,
    messages: list[dict],
    state: CallState,
) -> dict:
    """
    Main brain function — called once per conversation turn.

    Args:
        system_prompt: Built by prompts.build_system_prompt(state) — contains
                       current discovery gaps, language lock, classification context.
        messages: Conversation history [{role, content}, ...]. Last entry is
                  the latest user utterance.
        state: Current call state (used for fallback response only).

    Returns:
        Decision dict with keys: say, language, discovery, classification,
        confidence, barrier, callback_phrase, fire_whatsapp_now.
        NEVER raises — returns fallback on any error to keep the call alive.
    """
    if not messages:
        logger.warning("[llm] think() called with empty messages — returning fallback")
        return _fallback_response(state)

    provider = config.LLM_PROVIDER.lower()

    # Truncate conversation history to the last 8 messages to prevent free-tier 
    # TPM (Tokens Per Minute) rate limits on Groq/Gemini during long calls.
    messages = messages[-8:]

    try:
        # Hard 3-second timeout — if we take longer, the conversation feels dead
        raw = await asyncio.wait_for(
            _call_gemini(system_prompt, messages) if provider == "gemini"
            else _call_groq(system_prompt, messages),
            timeout=3.0,
        )
        result = _parse_response(raw)
        logger.info(
            f"[llm] turn done | classification={result['classification']} "
            f"confidence={result['confidence']:.0%} | say='{result['say'][:60]}...'"
        )
        return result

    except asyncio.TimeoutError:
        logger.error(f"[llm] {provider} timed out after 3s — returning fallback")
        return _fallback_response(state)

    except json.JSONDecodeError as e:
        logger.error(f"[llm] JSON parse failed: {e} — returning fallback")
        return _fallback_response(state)

    except Exception as e:
        logger.error(f"[llm] Unexpected error ({type(e).__name__}): {e} — returning fallback")
        return _fallback_response(state)
