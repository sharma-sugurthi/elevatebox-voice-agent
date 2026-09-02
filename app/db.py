"""
app/db.py — Turso persistence layer using the HTTP API directly.

We use httpx to call Turso's v2/pipeline HTTP endpoint instead of the
libsql_client Python package. The libsql_client package tries to use
WebSocket (wss://) connections which fail on Heroku's routing layer.
The HTTP API is simpler, more reliable, and avoids the dependency entirely.
"""

import json
import logging
import httpx
from app.config import TURSO_DATABASE_URL, TURSO_AUTH_TOKEN

logger = logging.getLogger(__name__)

# Build the HTTP pipeline URL from the libsql:// URL
_pipeline_url = ""
if TURSO_DATABASE_URL:
    _pipeline_url = TURSO_DATABASE_URL.replace("libsql://", "https://") + "/v2/pipeline"


def _arg(value):
    """Convert a Python value to Turso typed argument format."""
    if value is None:
        return {"type": "null"}
    elif isinstance(value, bool):
        return {"type": "integer", "value": str(int(value))}
    elif isinstance(value, int):
        return {"type": "integer", "value": str(value)}
    elif isinstance(value, float):
        return {"type": "float", "value": value}
    else:
        return {"type": "text", "value": str(value)}


async def _execute(sql: str, args: list = None) -> None:
    """POST a single SQL statement to Turso's HTTP pipeline API."""
    if not _pipeline_url or not TURSO_AUTH_TOKEN:
        return

    stmt = {"sql": sql}
    if args:
        stmt["args"] = [_arg(a) for a in args]

    payload = {
        "requests": [
            {"type": "execute", "stmt": stmt},
            {"type": "close"},
        ]
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.post(
            _pipeline_url,
            headers={
                "Authorization": f"Bearer {TURSO_AUTH_TOKEN}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if resp.status_code != 200:
            logger.error(f"[db] Turso HTTP error {resp.status_code}: {resp.text}")
        resp.raise_for_status()


async def init_db():
    """Create the calls table if it does not exist."""
    if not _pipeline_url:
        logger.warning("[db] TURSO_DATABASE_URL not set. Skipping schema init.")
        return
    try:
        await _execute("""
            CREATE TABLE IF NOT EXISTS calls (
                call_id TEXT PRIMARY KEY,
                language TEXT,
                budget TEXT,
                sells TEXT,
                product_count TEXT,
                timeline TEXT,
                features TEXT,
                classification TEXT DEFAULT 'cold',
                confidence REAL DEFAULT 0.0,
                barrier TEXT,
                whatsapp_sent INTEGER DEFAULT 0,
                callback_booked TEXT,
                transcript TEXT DEFAULT '[]',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        logger.info("[db] Database schema initialized.")
    except Exception as e:
        logger.error(f"[db] Failed to initialize database: {e}")


async def sync_state_to_turso(state) -> None:
    """
    Write-through cache: push current in-memory call state to Turso.
    Called as asyncio.create_task() so it never blocks the voice response.
    """
    if not _pipeline_url:
        return
    try:
        features_json = json.dumps(state.discovery.features)
        transcript_json = json.dumps(state.transcript)
        cb_booked = state.callback_booked.isoformat() if state.callback_booked else None

        await _execute(
            """
            INSERT INTO calls (
                call_id, language, budget, sells, product_count, timeline, features,
                classification, confidence, barrier, whatsapp_sent, callback_booked,
                transcript, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(call_id) DO UPDATE SET
                language=excluded.language,
                budget=excluded.budget,
                sells=excluded.sells,
                product_count=excluded.product_count,
                timeline=excluded.timeline,
                features=excluded.features,
                classification=excluded.classification,
                confidence=excluded.confidence,
                barrier=excluded.barrier,
                whatsapp_sent=excluded.whatsapp_sent,
                callback_booked=excluded.callback_booked,
                transcript=excluded.transcript,
                updated_at=CURRENT_TIMESTAMP
            """,
            [
                state.call_id, state.language, state.discovery.budget,
                state.discovery.sells, state.discovery.product_count,
                state.discovery.timeline, features_json,
                state.classification, state.confidence, state.barrier,
                1 if state.whatsapp_sent else 0, cb_booked, transcript_json,
            ],
        )
    except Exception as e:
        logger.error(f"[db] Failed to sync state to Turso: {e}")


async def close_db() -> None:
    """No persistent connections to close with the HTTP API."""
    pass
