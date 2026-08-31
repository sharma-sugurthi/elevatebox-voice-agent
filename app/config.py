"""
app/config.py — single place for all environment variables.

Loads from .env (gitignored) via python-dotenv.
Fails FAST with a clear error if a CRITICAL key is missing.
Non-critical keys (WhatsApp, Vapi) are optional — the brain works without them.
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _require(key: str) -> str:
    """Get an env var or raise a clear error immediately on startup."""
    value = os.getenv(key)
    if not value:
        raise RuntimeError(
            f"[config] Required env var '{key}' is missing or empty. "
            f"Check your .env file against .env.example."
        )
    return value


def _optional(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _warn_if_missing(key: str, feature: str) -> str:
    """Return value or empty string + warning. App still starts."""
    value = os.getenv(key, "")
    placeholder_values = {"", "xxx", "placeholder",
                          "YOUR_VAPI_KEY_HERE", "YOUR_VAPI_PHONE_NUMBER_ID_HERE",
                          "YOUR_WHATSAPP_PERMANENT_TOKEN_HERE",
                          "YOUR_WHATSAPP_PHONE_NUMBER_ID_HERE",
                          "YOUR_HEROKU_APP.herokuapp.com"}
    if not value or value in placeholder_values:
        logger.warning(f"[config] {key} not set — {feature} will be disabled.")
        return ""
    return value


# ── LLM (REQUIRED — the brain can't work without this) ───────────────────────
LLM_PROVIDER: str = _optional("LLM_PROVIDER", "gemini")
GEMINI_API_KEY: str = _require("GEMINI_API_KEY")
GROQ_API_KEY: str = _optional("GROQ_API_KEY")

# ── Vapi (OPTIONAL — needed for live calls, not for brain testing) ────────────
VAPI_API_KEY: str = _warn_if_missing("VAPI_API_KEY", "outbound call trigger")
VAPI_PHONE_NUMBER_ID: str = _warn_if_missing("VAPI_PHONE_NUMBER_ID", "outbound call trigger")

# ── WhatsApp (OPTIONAL — needed for live WhatsApp sends) ──────────────────────
WHATSAPP_TOKEN: str = _warn_if_missing("WHATSAPP_TOKEN", "WhatsApp messaging")
WHATSAPP_PHONE_NUMBER_ID: str = _warn_if_missing("WHATSAPP_PHONE_NUMBER_ID", "WhatsApp messaging")
WHATSAPP_HOTLEAD_TEMPLATE: str = _optional("WHATSAPP_HOTLEAD_TEMPLATE", "hot_lead_followup")
WHATSAPP_POSTCALL_TEMPLATE: str = _optional("WHATSAPP_POSTCALL_TEMPLATE", "post_call_summary")

# ── App (REQUIRED) ────────────────────────────────────────────────────────────
EVALUATOR_PHONE: str = _optional("EVALUATOR_PHONE", "+918688664337")
MY_PHONE: str = _optional("MY_PHONE", "+919392521762")
PUBLIC_BASE_URL: str = _optional("PUBLIC_BASE_URL", "http://localhost:8000")

# ── Feature flags (derived from config) ───────────────────────────────────────
WHATSAPP_ENABLED: bool = bool(WHATSAPP_TOKEN and WHATSAPP_PHONE_NUMBER_ID)
VAPI_ENABLED: bool = bool(VAPI_API_KEY and VAPI_PHONE_NUMBER_ID)
