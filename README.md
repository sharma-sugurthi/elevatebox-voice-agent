# ElevateBox Voice Agent

An autonomous AI voice agent that holds real sales conversations about e-commerce website development. Built as a hiring assignment for ElevateBox.

## What It Does

- **Calls a prospect** and pitches e-commerce website development naturally
- **Detects language** (Telugu, Hindi, English) and stays in it, handles code-switching
- **Asks discovery questions** naturally: budget, what they sell, product count, timeline, features
- **Classifies intent** (Hot / Warm / Cold) from **indirect signals**, not keywords
- **Fires WhatsApp mid-call** when a lead goes hot (before the call ends)
- **Books callbacks** from vague spoken times ("tomorrow morning" = next day at 10am IST)
- **Sends post-call summary** via WhatsApp with conversation context

## Architecture

```
Caller --> Vapi (voice + telephony) --> /chat/completions (Gemini brain)
                                              |
                                    State machine + scheduler
                                              |
                               /vapi/webhook --> WhatsApp (fire-and-forget)
```

**Design principle:** The LLM extracts and understands. Deterministic Python decides and acts. One Gemini call per turn, then plain Python for state/routing/triggering/scheduling.

## Tech Stack

| Layer | Tool | Why |
|-------|------|-----|
| LLM (brain) | Gemini 2.0 Flash | Free tier, low latency, best free Telugu/Hindi support |
| Voice + telephony | Vapi | Wraps STT + TTS + barge-in handling |
| WhatsApp | Meta Cloud API | Free tier, template-based messaging |
| Server | FastAPI + Uvicorn | Async, fast, Python-native |
| Hosting | Heroku | Stable public webhook URL |
| Fallback LLM | Groq (Llama 3.3 70B) | Swap via `LLM_PROVIDER` env var |

## Project Structure

```
elevatebox/
  app/
    main.py          # FastAPI server (4 endpoints)
    llm.py           # Gemini adapter with 3s timeout + Groq fallback
    prompts.py       # Dynamic system prompt, rebuilds every turn
    state.py         # Per-call state machine (discovery, classification)
    scheduler.py     # Deterministic callback time parser
    whatsapp.py      # Meta Cloud API adapter with retry
    config.py        # Environment loader with graceful degradation
  tests/             # 88 unit/integration tests
  docs/              # Architecture docs, tech decisions, build log
  Procfile           # Heroku process definition
  requirements.txt   # Pinned dependencies
```

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Uptime check |
| `POST` | `/chat/completions` | Vapi Custom LLM brain (OpenAI-compatible) |
| `POST` | `/vapi/webhook` | Call lifecycle events (inbound + end-of-call) |
| `POST` | `/call/trigger` | Initiate outbound call via Vapi API |

## Testing

```bash
# Run all 88 tests (no API calls, no cost)
pytest tests/ -v
```

All tests use mocked external services. Zero API cost.

## Setup

```bash
# Clone and install
git clone https://github.com/YOUR_USERNAME/elevatebox-voice-agent.git
cd elevatebox-voice-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Fill in your API keys

# Run locally
uvicorn app.main:app --reload --port 8000
```

## Key Engineering Decisions

1. **One LLM call per turn** -- keeps latency under 3 seconds
2. **Deterministic scheduling** -- callback time parsing is pure Python, no LLM arithmetic
3. **Discovery field protection** -- once captured, values are never overwritten by LLM hallucinations
4. **Language lock** -- detected on first turn, locked forever (prevents flip-flopping)
5. **Fire-and-forget WhatsApp** -- async background task, never blocks the voice response
6. **Graceful degradation** -- server starts without WhatsApp/Vapi keys, brain works standalone

## Author

Sugurthi Lavanya | +91 9392521762
