# Deliverables & Build Order

## Build order (get a ringing phone FAST, then add brains)
Ship each milestone before starting the next. A connecting call beats a perfect plan.

### Milestone 1 — The phone rings (targets the 25-pt item)
- [ ] Vapi account + a phone number that can place outbound calls.
- [ ] `POST /call/start` triggers Vapi to dial 8688664337 on its own.
- [ ] Agent speaks one scripted opening line when answered.
- [ ] `GET /health` works; service deployed somewhere publicly reachable (Vapi must reach the webhook).
**Done = the number rings by itself and a voice talks. Most candidates never get here.**

### Milestone 2 — Real conversation (rest of the 25-pt item + discovery 10 pts + language 10 pts)
- [ ] `/vapi/webhook` receives turns, calls LLM, returns natural replies.
- [ ] Discovery state machine: collects budget / sells / product_count / timeline / features, woven not listed.
- [ ] Language detect + lock (Telugu / Hindi / English), handles code-switching.
- [ ] Handles interruption (Vapi barge-in) without breaking.

### Milestone 3 — The differentiator (classification 15 pts + mid-call WhatsApp 15 pts)
- [ ] Classifier reads Hot/Warm/Cold from indirect answers (examples from docs/03).
- [ ] On HOT: mid-call WhatsApp fires as a background task, once, before call ends.
- [ ] Different action per state (hot=whatsapp+sell, warm=capture barrier+callback, cold=brochure+wrap).
**This is where the points everyone drops live. Spend the most time here.**

### Milestone 4 — Scheduling + post-call follow-up (10 pts + 10 pts)
- [ ] Parse spoken vague time -> real datetime -> book -> confirm verbally.
- [ ] Post-call WhatsApp with the 4 REQUIRED items (below).

### Milestone 5 — Harden + package (engineering judgment 5 pts)
- [ ] Latency check: replies feel live, not laggy.
- [ ] Failure handling: LLM timeout, WhatsApp fail, early hangup.
- [ ] Clean README, .env.example, .gitignore (no secrets committed).
- [ ] Hand-drawn architecture diagram photographed.
- [ ] <200-word note: what works, what doesn't, what you'd build next.

## The post-call WhatsApp MUST contain all four (Section 06 — 10 pts)
1. **Context of the call** — specific: the budget they named, timeline, features they asked about.
   Specifics from THIS conversation, not a generic summary.
2. **Proper framing** — reads like a human wrote it after a real call, not a log file dump.
3. **Your mobile number** — clearly visible so they can call back without hunting.
4. **An image of how you built it** — the hand-drawn architecture photo.
Plus: **your resume** attached (auto-attach if the system can; manual is acceptable).

## What to SEND to 8688664337 (Section 06)
- [ ] The working prototype, live, that can call the number on demand.
- [ ] One-page architecture diagram (image or PDF) — the hand-drawn one.
- [ ] Short note under 200 words: what works, what doesn't, what's next.
- [ ] Your resume.
- [ ] Your mobile number.
- [ ] Repo link (optional but do it — it shows the clean code).

## DO NOT SEND (they explicitly reject these)
- A presentation / deck explaining how you would build it.
- A plan, proposal, or estimate.
- A demo video INSTEAD of a working system.
- Anything that needs them to install something to see it work.

## The honesty clause (use it if you run out of time)
Their words: if the call connects but classification is weak, SEND IT ANYWAY with a note on
what you'd fix. "Honest partial work with clear thinking" beats nothing. So there is no reason
to not submit. Ship whatever works by your self-imposed deadline + the note.

## Scorecard reminder (60 = callback)
25 conversation · 15 classification · 15 mid-call action · 10 language · 10 discovery ·
10 scheduling · 10 follow-up · 5 engineering judgment.
Milestones 1-3 alone, done well, clear 60. Everything after is upside.
