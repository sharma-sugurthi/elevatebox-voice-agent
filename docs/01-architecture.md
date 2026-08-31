# Architecture

## The shape
```
                        [ The lead, on a phone call: 8688664337 ]
                                        |
                                        v
                        +-------------------------------+
                        |   VAPI  (telephony + voice)   |
                        |  outbound dial, STT, TTS,     |
                        |  barge-in / turn-taking       |
                        +-------------------------------+
                                        |  live transcript turns (webhook)
                                        v
                        +-------------------------------+
                        |   FASTAPI  "decision engine"  |
                        |  - discovery state machine    |
                        |  - LLM: understand + classify |
                        |  - decide next utterance       |
                        |  - decide next action          |
                        +-------------------------------+
                             |            |            |
              async, non-blocking         |            |
                             v            v            v
                     [ WhatsApp ]   [ Scheduler ]  [ next utterance
                     fires mid-call  callback booked  back to Vapi ]
```

## Why this stack
- **Vapi owns the hard real-time parts** (dialing, low-latency STT/TTS, interruption handling).
  We do NOT hand-roll Twilio + separate STT/TTS — that burns the whole timeline on plumbing.
- **FastAPI owns the intelligence** — the part actually being scored and the part we're strongest at.
  Vapi calls our webhook on each user turn; we return what to say and whether to fire an action.

## Request/response flow (per conversation turn)
1. Callee speaks -> Vapi transcribes -> POST to our `/vapi/webhook` with transcript + call state.
2. FastAPI:
   a. Update discovery state (which of budget/products/timeline/features we still need).
   b. Run classification pass on cumulative transcript -> Hot/Warm/Cold + confidence + detected barrier.
   c. If Hot and WhatsApp not yet sent -> spawn background task to send mid-call WhatsApp. Do not await.
   d. If a callback time was spoken -> parse to datetime -> book -> confirm verbally next turn.
   e. Produce next agent utterance (sales + next needed discovery question).
3. Return utterance to Vapi -> Vapi speaks it. Loop.

## Endpoints (FastAPI)
- `POST /vapi/webhook`   — main per-turn brain. Must return fast (< ~800ms of our own logic).
- `POST /call/start`     — triggers the outbound call via Vapi API (this is "dials on its own").
- `GET  /health`         — trivial, for uptime checks.
- (internal) `send_whatsapp(kind, context)` — async helper, not a blocking endpoint call.

## State
Keep per-call state in memory keyed by Vapi call_id (a dict is fine for a prototype;
note in build log that production would use Redis). Store: language locked-in, discovery
answers collected, current classification, whatsapp_sent flag, callback booking.

## The latency rule
Our webhook's own compute budget is small. The LLM call for "understand + next utterance"
is the main cost. Keep ONE LLM call per turn where possible (combine classify + respond in a
single structured-output prompt — see docs/02 and docs/03). Never make the voice loop wait on
WhatsApp/scheduler I/O; those are background tasks.

## Failure handling (scored under engineering judgment)
- If the LLM call times out -> return a safe generic clarifying line ("Sorry, could you say that again?")
  so the call never dead-airs.
- If WhatsApp send fails -> log it, retry once in background, still send the post-call message.
- If callee hangs up -> fire the post-call follow-up WhatsApp from last known state.

## The hand-drawn diagram (SCORED, Section 06 item 4)
Redraw THIS shape by hand on paper, photograph it. They explicitly say hand-drawn is fine and
they want to see how you think, not diagram-tool polish. Do not skip this — it's a required
deliverable item.
