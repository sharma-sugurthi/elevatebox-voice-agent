# Tech Decisions (pinned — the agent must follow these, not re-decide)

These are locked choices made under a real constraint: **minimal budget, quality still matters,
low-RAM i3 laptop, Heroku available via GitHub Student Pack.** Where a choice is a fallback,
it's marked so the agent can swap without redesigning.

## LLM (the brain) — Google Gemini 2.0 Flash
- **Why:** free API tier without a credit card, low latency (critical — latency is our #1 scored
  risk), native structured/JSON output, and the best Telugu/Hindi handling among free options
  (Google's Indian-language investment).
- **Rate limit is the risk.** A live call makes one LLM call PER TURN (~15-25 calls in a 3-min call).
  Free-tier limits can be tight. Mitigation: keep to ONE LLM call per turn (combine classify+respond,
  see docs/02 + docs/03), and test heavily before the real evaluation call.
- **Swappability is mandatory.** Put ALL LLM access behind one adapter module (`app/llm.py`) with a
  single function `def think(system, transcript, state) -> dict`. If Gemini's rate limit bites on
  the live call, we swap to the fallback by changing one module, not the whole brain.
- **Fallback:** Groq (Llama 3.3 70B) — even faster, free tier, but weaker Telugu. Wire the adapter
  so switching is a config flag: `LLM_PROVIDER=gemini|groq`.

## Telephony + voice — Vapi
- **Not free** — bills per call minute and needs a card. This is the ONE place we likely spend a
  few dollars. The assignment explicitly reimburses API spend on joining and says "cost is not the
  filter," so a few dollars of Vapi trial credit for building + evaluation calls is expected/acceptable.
- **Why still Vapi:** it wraps outbound telephony + STT + TTS + barge-in in one API. Hand-rolling
  Twilio + separate STT/TTS would burn the whole timeline on real-time plumbing.
- **Fallback if Vapi outbound is blocked or credit runs out:** Twilio trial credit + the developer's
  existing career-support-voice-agent (LiveKit) code. Log the switch if it happens.
- **Keep the brain OUT of Vapi.** Use Vapi only for voice I/O; do classification/decision in our
  FastAPI so we control the 30 points that live in classification + mid-call action.

## WhatsApp — Meta WhatsApp Cloud API
- **Why:** free for our volume (1,000 conversations/month free tier); Twilio WhatsApp adds per-message
  cost on top of Meta.
- **CRITICAL PREREQUISITE — do this on day 1, before writing send code:**
  WhatsApp does NOT allow free-form messages to someone who hasn't messaged you in the last 24h.
  The evaluator is a cold outbound call — they have NOT messaged us. Therefore the mid-call "hot lead"
  message MUST be a **pre-approved Message Template** submitted to Meta in advance (approval takes a
  few hours to ~1 day). Design the hot-lead message as a template with variables for the specific
  context. The POST-call follow-up may also need a template unless the evaluator replies first.
  **If this prerequisite is skipped, the mid-call WhatsApp silently fails. It is not a code detail —
  it is a day-1 blocker.**
- Adapter: put WhatsApp behind `app/whatsapp.py` with `async def send(template, to, vars)`.

## Hosting — Heroku (GitHub Student Pack credits)
- **Why:** the webhook runs on Heroku's servers, so the i3/low-RAM laptop doesn't matter, and Vapi
  gets a stable public HTTPS URL (better than an ngrok tunnel off a laptop that drops).
- Needs a `Procfile`: `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Gotcha:** free/eco dynos sleep when idle; the first request after sleep is slow. Before triggering
  the evaluation call, hit `GET /health` once to WARM the dyno so the first real turn isn't laggy.
- Local dev on the laptop is fine for logic, but Vapi must hit the Heroku URL for real calls.

## Language & runtime
- Python 3.12, FastAPI, uvicorn. `httpx` for async outbound calls (Gemini, WhatsApp).
- Keep dependencies minimal — the laptop is weak and Heroku slugs should stay small.

## State storage — in-memory dict for the prototype
- Per-call state keyed by Vapi `call_id` in a module-level dict. Good enough for a prototype.
- **Note for the "defend your choices" answer:** production would use Redis (Heroku Redis add-on)
  because dynos restart and lose memory, and multiple dynos wouldn't share a dict. State it in the log.

## The one-LLM-call-per-turn rule (latency + rate-limit survival)
Every turn, `app/llm.py::think()` returns BOTH the spoken line AND the decision JSON
(classification, discovery updates, callback phrase, fire_whatsapp_now) in a single structured
response. Do NOT make separate calls for "understand" then "classify" then "respond" — that
triples latency and rate-limit burn and will break a live call.
