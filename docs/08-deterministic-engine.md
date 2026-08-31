# Deterministic Engine — LLM only where it's actually needed

## The principle
The LLM is expensive (latency + credits + rate limit). Use it ONLY for what genuinely requires
natural-language understanding. Everything else is plain deterministic Python. This is scored
under engineering judgment AND it's the main cost/latency control.

**Shape: the LLM extracts and understands; Python decides and acts.**

## What the LLM (Gemini) does — the ONLY things it does
One structured-output call per turn returns:
1. Understanding of messy, vague, code-switching human speech (Python cannot do this).
2. Classification from indirect signals ("my brother handles this" -> warm + not_decision_maker).
3. The next natural spoken line, in the locked language.

That's it. The LLM returns DATA + one line to speak. It does not route, trigger, schedule, or
manage state.

## What deterministic Python does — no LLM calls
| Job | How (deterministic) |
|-----|---------------------|
| Track discovery progress | dict of {budget, sells, product_count, timeline, features}; check which are still null |
| Pick next discovery question | if budget is None: ask budget; elif timeline is None: ask timeline; ... |
| Fire mid-call WhatsApp | `if classification == "hot" and not state.whatsapp_sent: send(); state.whatsapp_sent = True` |
| Resolve callback time | map table + dateutil: "morning"->10:00, "after lunch"->14:00, "evening"->18:00; add to today/tomorrow |
| Lock language | store first detected language in state; never re-decide |
| Fill WhatsApp template vars | Python string formatting from state |
| Decide the per-state action | hot->whatsapp+continue; warm->capture barrier+offer callback; cold->brochure+wrap. A dict/if-tree. |
| Dedup / once-only actions | boolean flags in state |

## The time-resolution table (deterministic, no LLM)
```python
TIME_OF_DAY = {
    "morning": time(10, 0),
    "afternoon": time(14, 0),
    "after lunch": time(14, 0),
    "evening": time(18, 0),
    "night": time(20, 0),
}
# LLM extracts the phrase ("tomorrow morning") into {day_offset: 1, part: "morning"}.
# Python turns that into a real datetime and Python confirms it verbally.
```
The LLM only pulls out the rough phrase. Python does the actual date math. This is more reliable
than asking the LLM to compute timestamps (LLMs are bad at date arithmetic) AND it's free.

## The single-LLM-call-per-turn contract
`app/llm.py::think()` makes exactly ONE Gemini call per turn and returns the full decision dict
(see docs/02 schema). The webhook then runs only deterministic Python on that dict. Never make
a second LLM call in the same turn to "double check" or "also classify" — it's already in the one
response.

## Why this matters (three wins at once)
- **Cost:** ~1/3 the LLM calls of a naive design -> ~1/3 the credit/rate-limit burn.
- **Latency (scored):** one model round-trip per turn, not three. The call feels live.
- **Defensibility (scored):** "I used the LLM only for language understanding and classification;
  everything deterministic is deterministic Python, so it's fast, cheap, and testable." That's a
  strong answer to "defend your choices."

## Free testing consequence (huge)
Because the decision logic is deterministic Python, you can UNIT TEST the entire brain with typed
fake transcripts and ZERO phone calls and ZERO paid minutes. Only the final voice integration
needs real calls. See docs/09-cost-control.md.
