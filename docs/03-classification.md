# Classification — Hot / Warm / Cold

## Why this doc exists
The assignment says most systems fail HERE. They transcribe well, then treat every caller
the same. Classification (15 pts) + the mid-call action it triggers (15 pts) = 30 of 100 points,
and it's the stated differentiator. This is where the assignment is won.

## The core insight (their words)
> "Real people do not say I am a hot lead. They say things like send me the details,
> my budget is not much right now, my brother handles this, or how soon can you start."

So classification must read INDIRECT signals, not keywords. An LLM classifier with good
examples beats any rule list. Give it the examples below in the prompt.

## The three states and their REQUIRED actions
| State | Signal | Action the system must take |
|-------|--------|-----------------------------|
| HOT   | High buying intent — asking price, timeline, "how soon can you start" | **Fire the WhatsApp before the call ends.** Then keep selling. |
| WARM  | Real need but a barrier: budget / timing / someone else decides | **Capture the barrier, schedule a callback.** Do not oversell. |
| COLD  | Curious, no clear need or budget, "just looking" | **Log it, offer to send a brochure, wrap up politely.** |

The label is not the point — the DIFFERENT ACTION is the point. A system that classifies
correctly but does the same thing anyway scores near zero here.

## Signal examples to put in the classifier prompt
HOT (indirect):
- "How soon can you start?"
- "What would something like this cost?"
- "Can you show me examples by tomorrow?"
- "I need this live before Diwali."

WARM (barrier present — capture WHICH barrier):
- "Send me the details, I'll look." (soft interest, timing barrier)
- "My budget isn't much right now." (budget barrier)
- "My brother/husband handles these decisions." (not_decision_maker barrier)
- "Maybe next month." (timing barrier)

COLD:
- "Just seeing what's out there."
- "Someone told me to ask around."
- "Not really looking to spend anything."

## Handling vagueness (explicitly scored)
People are vague. "Send me the details" is WARM, not COLD — there's interest but a barrier
(they're not committing on the call). The classifier must not dump every non-committal
person into COLD. When confidence is low, default UP one level (treat borderline cold as warm)
so you don't kill a real lead — and log the ambiguity.

## The mid-call WhatsApp trigger (15 pts — timing is everything)
- Fires the INSTANT classification flips to HOT with reasonable confidence, mid-conversation.
- Must NOT wait for the call to end. Must NOT block the voice loop (background task).
- Contains a short, relevant message referencing what they just showed interest in.
- Set a `whatsapp_sent` flag so it fires once, not every turn.

"The WhatsApp arrives while we are still talking" is in their "what will impress us" list.
This is the single most visible wow-moment. Make it fire reliably.

## Callback scheduling from vague speech (10 pts)
- "Call me tomorrow morning" -> resolve against current datetime -> e.g. next day 10:00 IST.
- "After lunch sometime" -> ~14:00 same or next day; confirm verbally: "So around 2pm tomorrow?"
- Always CONFIRM the resolved time out loud so the callee can correct it.
- Store the booking; the post-call follow-up should reference it.

## Test script before submitting
Call yourself (or a friend) and deliberately run each path:
1. Play HOT: ask about price and timeline -> confirm WhatsApp arrives DURING the call.
2. Play WARM: "my budget's tight right now" -> confirm it captures budget barrier + offers callback.
3. Play COLD: "just looking" -> confirm it wraps politely, logs, no hard sell.
4. Play vague: "send me details" -> confirm it lands WARM, not COLD.
5. Play callback: "call me tomorrow morning" -> confirm it books and confirms a real time.
Log each result in 05-build-log.md.
