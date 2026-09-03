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
GEMINI_API_KEY: str = _optional("GEMINI_API_KEY")
GROQ_API_KEY: str = _optional("GROQ_API_KEY")
GOOGLE_CREDENTIALS_JSON: str = _optional("GOOGLE_CREDENTIALS_JSON")

GCP_PROJECT_ID = ""
if GOOGLE_CREDENTIALS_JSON:
    import json
    try:
        creds = json.loads(GOOGLE_CREDENTIALS_JSON)
        GCP_PROJECT_ID = creds.get("project_id", "")
        creds_path = "/tmp/gcp_creds.json"
        with open(creds_path, "w") as f:
            f.write(GOOGLE_CREDENTIALS_JSON)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path
        LLM_PROVIDER = "gemini"  # Force Gemini when Vertex is active
        logger.info(f"Loaded Vertex AI credentials for project: {GCP_PROJECT_ID}")
    except Exception as e:
        logger.error(f"Failed to load GOOGLE_CREDENTIALS_JSON: {e}")
elif not GEMINI_API_KEY and LLM_PROVIDER == "gemini":
    raise RuntimeError("Missing GEMINI_API_KEY or GOOGLE_CREDENTIALS_JSON for Gemini provider")

# ── Database (Turso) ──────────────────────────────────────────────────────────
TURSO_DATABASE_URL: str = _warn_if_missing("TURSO_DATABASE_URL", "Persistent state storage")
TURSO_AUTH_TOKEN: str = _warn_if_missing("TURSO_AUTH_TOKEN", "Persistent state storage")

# ── Vapi (OPTIONAL — needed for live calls, not for brain testing) ────────────
VAPI_API_KEY: str = _warn_if_missing("VAPI_API_KEY", "outbound call trigger")
VAPI_PHONE_NUMBER_ID: str = _warn_if_missing("VAPI_PHONE_NUMBER_ID", "outbound call trigger")

# ── Plivo (OPTIONAL — needed for Plivo-triggered outbound calls) ──────────────
PLIVO_AUTH_ID: str = _warn_if_missing("PLIVO_AUTH_ID", "Plivo outbound calling")
PLIVO_AUTH_TOKEN: str = _warn_if_missing("PLIVO_AUTH_TOKEN", "Plivo outbound calling")
PLIVO_FROM_NUMBER: str = _optional("PLIVO_FROM_NUMBER", "")

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
PLIVO_ENABLED: bool = bool(PLIVO_AUTH_ID and PLIVO_AUTH_TOKEN and PLIVO_FROM_NUMBER)
