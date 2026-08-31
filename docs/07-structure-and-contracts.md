# Project Structure, Env Contract & API Contracts

The agent must build into THIS layout and keep to it across runs. Don't reorganize between runs.

## File tree
```
elevatebox-voice-agent/
├── CLAUDE.md
├── docs/                       # the context docs (already written)
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app, routes: /call/start, /vapi/webhook, /health
│   ├── llm.py                  # LLM adapter — think(system, transcript, state) -> dict. Gemini/Groq swap.
│   ├── whatsapp.py             # WhatsApp adapter — async send(template, to, vars)
│   ├── vapi_client.py          # starts outbound calls via Vapi API
│   ├── scheduler.py            # parse spoken vague time -> datetime, store bookings
│   ├── state.py                # per-call state store (in-memory dict keyed by call_id)
│   ├── prompts.py              # system prompt + classification examples (from docs/02, docs/03)
│   └── config.py               # loads env vars, one place
├── .env.example                # placeholder keys only — committed
├── .env                        # real keys — GITIGNORED, never committed
├── .gitignore
├── Procfile                    # web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
├── requirements.txt
└── README.md                   # what it does, how to run, architecture
```

## .env contract (exact variable names — agent must use these)
```
# LLM
LLM_PROVIDER=gemini                # gemini | groq
GEMINI_API_KEY=xxx
GROQ_API_KEY=xxx                   # only if fallback used

# Vapi (telephony + voice)
VAPI_API_KEY=xxx
VAPI_PHONE_NUMBER_ID=xxx           # the Vapi outbound number id
VAPI_ASSISTANT_ID=xxx              # if using a Vapi assistant wrapper

# WhatsApp (Meta Cloud API)
WHATSAPP_TOKEN=xxx
WHATSAPP_PHONE_NUMBER_ID=xxx
WHATSAPP_HOTLEAD_TEMPLATE=hot_lead_followup    # pre-approved template name
WHATSAPP_POSTCALL_TEMPLATE=post_call_summary   # pre-approved template name

# App
EVALUATOR_PHONE=8688664337         # the number to call (with country code in code: +918688664337)
MY_PHONE=+91xxxxxxxxxx             # developer's number, goes in the WhatsApp messages
PUBLIC_BASE_URL=https://<app>.herokuapp.com   # where Vapi sends webhooks
```
`.env.example` has these keys with `xxx`/placeholder values. `.env` has real values and is gitignored.
**Never commit real keys — the assignment reviewer will read the repo.**

## Vapi -> our webhook contract (POST /vapi/webhook)
Vapi calls our webhook on conversation events. The exact payload shape depends on the Vapi mode
the agent chooses (custom-LLM vs assistant + function calls); the agent must confirm this against
current Vapi docs, but design around this SHAPE:

Incoming (per user turn), roughly:
```json
{
  "message": {
    "type": "transcript" | "function-call" | "status-update" | "end-of-call-report",
    "call": { "id": "call_abc123", "customer": { "number": "+918688664337" } },
    "transcript": "what the callee just said",
    "role": "user"
  }
}
```

Our response (what Vapi speaks next):
```json
{ "assistantMessage": "the next spoken line" }
```
(Exact field name per Vapi's custom-LLM/response spec — agent verifies against live docs. The
POINT is: in = transcript + call id, out = next line to speak.)

Our webhook internally, each turn:
1. Load state for `call.id` from state.py (create if new).
2. Call `llm.think(system, running_transcript, state)` -> decision dict (see docs/02 schema).
3. Update discovery + classification in state.
4. If `fire_whatsapp_now` and not `state.whatsapp_sent`: spawn background task
   `whatsapp.send(hotlead_template, EVALUATOR_PHONE, vars=context)`, set flag. DO NOT await it.
5. If `callback_phrase`: `scheduler.parse_and_book(phrase)` -> confirm verbally next line.
6. Return `decision["say"]` to Vapi.
On `type == "end-of-call-report"`: fire the post-call WhatsApp with full context + resume note.

## /call/start (POST) — "dials on its own"
Triggers `vapi_client.start_call(EVALUATOR_PHONE)`. This is the endpoint you hit to make the
system call the evaluator. No human dialing = this endpoint does it.

## Definition of done, per milestone (agent self-checks these)
- M1 done: hitting /call/start makes +918688664337 ring and hear one spoken opening line.
- M2 done: a full back-and-forth happens; discovery fields fill; language stays consistent.
- M3 done: on a hot-intent reply, a WhatsApp template arrives on the phone DURING the call, once.
- M4 done: "call me tomorrow morning" produces a confirmed booked time; post-call WhatsApp has all 4 items.
- M5 done: latency feels live; LLM/WhatsApp failures don't dead-air; README+.env.example+.gitignore clean.

## requirements.txt (minimum)
```
fastapi
uvicorn[standard]
httpx
google-generativeai        # gemini
python-dotenv
python-dateutil            # vague-time parsing help
```
(add groq only if fallback wired)
