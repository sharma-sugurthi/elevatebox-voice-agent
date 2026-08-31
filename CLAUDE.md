# Project: ElevateBox Outbound Sales Voice Agent

## What this is
An autonomous AI voice system that places an outbound phone call, holds a real sales
conversation about e-commerce website development, reads how serious the buyer is, and
takes action (WhatsApp, callback booking) while the call is still live.

This is a hiring assignment. Selection is: **the system calls the number, it works, they call back.**
No resume screen, no interview gate. The working call IS the application.

## The one target number
The system must call **8688664337** on its own and hold a conversation. This is the
evaluator's phone. Everything is judged on that live call.

## Non-negotiable constraints (from the assignment)
1. The system dials by itself. No human dialing, no human on the line.
2. Speaks Telugu, Hindi, or English — and STAYS in whichever language the callee answers in.
   Code-switching (Telugu+English mid-sentence) is normal here and must not break it.
3. Sells e-commerce website development conversationally, not as a recorded script.
4. Asks discovery questions naturally: budget, what they sell, number of products, timeline, features.
5. Classifies the caller Hot / Warm / Cold from INDIRECT answers (see docs/03-classification.md).
6. Fires a WhatsApp MID-CALL if intent is high — before the call ends, not after.
7. Books a callback from spoken vague time ("call me tomorrow morning" -> real datetime).
8. Sends a post-call WhatsApp with real conversation context + resume + my number + architecture image.

## What they are actually testing (quote from brief)
"Whether you can take an unclear problem, choose a stack, wire live services together,
handle the real world when it talks back, and ship something that works on the first call."

Translation for the agent: **prioritize a working end-to-end call over feature completeness.**
A call that connects and sells but misclassifies is worth more than a perfect classifier that never dials.

## Tech stack (PINNED — see docs/06-tech-decisions.md for the reasoning, don't re-decide)
- **LLM (the brain):** Google Gemini 2.0 Flash. Free tier, low latency, best free Telugu/Hindi.
  Behind a swappable adapter (app/llm.py); Groq is the fallback via LLM_PROVIDER flag.
- **Voice + telephony:** Vapi (wraps outbound telephony + STT + TTS + barge-in). NOT free — a few
  dollars of trial credit expected; assignment reimburses on joining. Twilio+LiveKit is the fallback.
- **WhatsApp:** Meta WhatsApp Cloud API (free tier). CRITICAL: cold outbound requires a PRE-APPROVED
  message template submitted to Meta on day 1 — approval takes hours. See docs/06. Not optional.
- **Hosting:** Heroku (GitHub Student Pack credits). Keeps the webhook off the low-RAM laptop and
  gives Vapi a stable public URL. Warm the dyno with /health before the evaluation call.
- **Language/runtime:** Python 3.12, FastAPI, uvicorn, httpx. Developer's strongest stack.

See docs/07-structure-and-contracts.md for the exact file tree, .env variable names, and the
Vapi<->FastAPI webhook contract. Build into that structure; keep it stable across agent runs.

## Architecture shape (see docs/01-architecture.md for detail)
Lead on call -> Vapi (telephony + voice in/out) -> FastAPI webhook (understanding + decision engine)
-> actions fire OUT while call is live (WhatsApp / scheduler) -> post-call follow-up.

## Priorities, in order (matches their 100-point scorecard)
1. [25 pts] Dials on its own + holds a real two-way conversation. **DO THIS FIRST.**
2. [15 pts] Intent classification from indirect answers. **THE THING EVERYONE FAILS. Second priority.**
3. [15 pts] WhatsApp fires mid-call, triggered by intent (not by call end).
4. [10 pts] Language handling incl. mixed sentences.
5. [10 pts] Discovery question quality.
6. [10 pts] Callback scheduling from vague speech.
7. [10 pts] Follow-up WhatsApp quality + the 4 required items.
8. [5 pts]  Engineering judgment you can defend.

60+ total gets a callback. Ship at 60, don't wait for 100.

## Hard engineering realities to design around
- **Latency:** if a reply takes 3 seconds the conversation is dead. Keep webhook logic fast;
  don't block the voice loop on a WhatsApp send — fire it async / fire-and-forget.
- **Interruption:** people talk over the bot. Vapi handles barge-in; don't fight it.
- **Mid-call action without blocking:** the WhatsApp send must NOT stall the conversation.
  Trigger it in a background task, keep talking.

## Working agreement for the agent
- Build in the order in docs/04-deliverables.md. Get a connecting call before adding intelligence.
- **LLM only where needed.** The LLM extracts and understands; deterministic Python decides and acts.
  One Gemini call per turn, then plain Python for state/routing/triggering/scheduling. See
  docs/08-deterministic-engine.md. This is scored (engineering judgment) and controls cost + latency.
- **Keep spend near zero.** Test the deterministic brain with TYPED fake transcripts and unit tests
  before making a single paid voice call. Budget cap ₹1,500. See docs/09-cost-control.md.
- After each milestone, append a dated entry to docs/05-build-log.md: what was built, what broke,
  what the fix was. This log becomes the developer's "defend your choices" notes (5 scored pts).
- Never fake a working feature. If something is stubbed, mark it `# STUB` and log it.
- Secrets go in a .env that is gitignored. Never commit API keys. (Assignment reviewer will see the repo.)
- Keep a .env.example with placeholder keys only.
