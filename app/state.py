"""
app/state.py — per-call state store.

Keeps a dict of CallState objects keyed by Vapi call_id.
In-memory for prototype — production would use Redis
(Heroku dynos restart and lose memory; multiple dynos wouldn't share a dict).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class DiscoveryState:
    """Tracks what we've learned about the prospect during the call."""
    budget: Optional[str] = None
    sells: Optional[str] = None           # what they sell
    product_count: Optional[str] = None
    timeline: Optional[str] = None
    features: list = field(default_factory=list)

    def missing_fields(self) -> list[str]:
        """Returns list of discovery fields we still haven't captured."""
        missing = []
        if not self.budget:
            missing.append("budget")
        if not self.sells:
            missing.append("sells")
        if not self.product_count:
            missing.append("product_count")
        if not self.timeline:
            missing.append("timeline")
        if not self.features:
            missing.append("features")
        return missing

    def is_complete(self) -> bool:
        return len(self.missing_fields()) == 0


@dataclass
class CallState:
    """Full state for one active call, keyed by Vapi call_id."""

    call_id: str

    # Language — locked after first detection, never changed
    language: Optional[str] = None        # "te" | "hi" | "en"

    # Discovery — filled in as call progresses
    discovery: DiscoveryState = field(default_factory=DiscoveryState)

    # Classification — updated each turn
    classification: str = "cold"          # "hot" | "warm" | "cold"
    confidence: float = 0.0
    barrier: Optional[str] = None         # "budget" | "timing" | "not_decision_maker" | None

    # Action flags — once-only, prevent duplicate fires
    whatsapp_sent: bool = False           # mid-call hot-lead WhatsApp
    callback_booked: Optional[datetime] = None

    # Running transcript history (list of {"role": "user"|"assistant", "content": str})
    transcript: list = field(default_factory=list)


# ── Module-level store (the in-memory dict) ───────────────────────────────────
_store: dict[str, CallState] = {}


def get_or_create(call_id: str) -> CallState:
    """Return existing state for call_id, or create a fresh one."""
    if call_id not in _store:
        _store[call_id] = CallState(call_id=call_id)
    return _store[call_id]


def get(call_id: str) -> Optional[CallState]:
    """Return state for call_id, or None if not found."""
    return _store.get(call_id)


def update_from_llm(call_id: str, llm_output: dict) -> CallState:
    """
    Merge LLM output dict into existing call state.
    Rules:
    - Language: set once, never overwrite.
    - Discovery fields: only fill null fields, never overwrite captured values.
    - Classification/confidence/barrier: always update (LLM has full transcript context).
    - fire_whatsapp_now and callback_phrase are READ here but not stored
      (the webhook handler acts on them and sets the boolean flags).
    """
    state = get_or_create(call_id)

    # Language lock — set once only
    if state.language is None and llm_output.get("language"):
        state.language = llm_output["language"]

    # Discovery merge — never overwrite a value we already captured
    disc = llm_output.get("discovery", {})
    if disc:
        if not state.discovery.budget and disc.get("budget"):
            state.discovery.budget = disc["budget"]
        if not state.discovery.sells and disc.get("sells"):
            state.discovery.sells = disc["sells"]
        if not state.discovery.product_count and disc.get("product_count"):
            state.discovery.product_count = disc["product_count"]
        if not state.discovery.timeline and disc.get("timeline"):
            state.discovery.timeline = disc["timeline"]
        if not state.discovery.features and disc.get("features"):
            state.discovery.features = disc["features"]

    # Classification — always update
    if llm_output.get("classification"):
        state.classification = llm_output["classification"]
    if llm_output.get("confidence") is not None:
        state.confidence = float(llm_output["confidence"])
    if llm_output.get("barrier"):
        state.barrier = llm_output["barrier"]

    return state


def append_transcript(call_id: str, role: str, content: str) -> None:
    """Add a turn to the running transcript."""
    state = get_or_create(call_id)
    state.transcript.append({"role": role, "content": content})


def clear(call_id: str) -> None:
    """Remove call state (cleanup after end-of-call)."""
    _store.pop(call_id, None)
