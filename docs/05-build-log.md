# Build Log

Append a dated entry after each work session. This is not busywork — it becomes your
"explain every decision you made and what you'd fix next" material (5 scored pts, and the
required <200-word note). Write what you built, what broke, and why you chose what you chose.

Format:
```
## YYYY-MM-DD — <milestone / session>
Built:
Broke / surprised me:
Decision + why:
Next:
```

---

## 2026-08-25 — Setup
Built: repo scaffold, context docs (CLAUDE.md + docs/01-05).
Decision + why: Chose Vapi over hand-rolled Twilio+STT+TTS to avoid burning the timeline on
real-time plumbing; FastAPI for the decision engine because it's my strongest stack and the
brain is what's actually scored.
Next: Milestone 1 — get 8688664337 to ring from /call/start with one spoken opening line.

<!-- Add entries below as you build. Keep them honest — stubbed features get marked, not hidden. -->
