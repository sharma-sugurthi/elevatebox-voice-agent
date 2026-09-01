import json
import logging
import libsql_client
from app.config import TURSO_DATABASE_URL, TURSO_AUTH_TOKEN

logger = logging.getLogger(__name__)

# Global client
_client = None

def get_client():
    """Get or create the global libsql client."""
    global _client
    if _client is None:
        if not TURSO_DATABASE_URL:
            logger.warning("[db] TURSO_DATABASE_URL is not set. Database operations will fail.")
        _client = libsql_client.create_client(
            url=TURSO_DATABASE_URL or "file:///tmp/elevatebox.db",
            auth_token=TURSO_AUTH_TOKEN
        )
    return _client

async def init_db():
    """Initialize the database schema."""
    client = get_client()
    if not client: return
    try:
        await client.execute('''
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
        ''')
        logger.info("[db] Database schema initialized.")
    except Exception as e:
        logger.error(f"[db] Failed to initialize database: {e}")

async def sync_state_to_turso(state):
    """Write-through cache: pushes in-memory state to Turso instantly."""
    client = get_client()
    if not client: return
    try:
        features_json = json.dumps(state.discovery.features)
        transcript_json = json.dumps(state.transcript)
        cb_booked = state.callback_booked.isoformat() if state.callback_booked else None

        await client.execute('''
            INSERT INTO calls (
                call_id, language, budget, sells, product_count, timeline, features,
                classification, confidence, barrier, whatsapp_sent, callback_booked, transcript, updated_at
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
        ''', [
            state.call_id, state.language, state.discovery.budget, state.discovery.sells,
            state.discovery.product_count, state.discovery.timeline, features_json,
            state.classification, state.confidence, state.barrier,
            1 if state.whatsapp_sent else 0, cb_booked, transcript_json
        ])
    except Exception as e:
        logger.error(f"[db] Failed to sync state to Turso: {e}")

async def close_db():
    """Close the global libsql client."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None

