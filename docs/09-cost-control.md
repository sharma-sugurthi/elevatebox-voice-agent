# Cost Control — keep out-of-pocket near zero

## Budget cap (hard rule for the agent and the developer)
Maximum out-of-pocket buffer: **₹1,500 (~$18).** Do NOT pre-load more. The free trials cover a
disciplined build; this buffer is insurance against running out mid-evaluation-call, not fuel.

## The free-credit sequence — exhaust in THIS order before spending anything
1. **Gemini 2.0 Flash** — free, no card. The brain. ₹0.
2. **WhatsApp Cloud API** — free tier (1,000 conversations/month). ₹0.
3. **Heroku** — GitHub Student Pack credits. ₹0.
4. **Vapi trial** — $10 ≈ ₹830, ~150-200 minutes. Card required. This is the finite one.
Only after Vapi trial runs low does real money enter, at ~₹8-12/min.

## The rule that keeps spend at or near ₹0: TEST THE BRAIN FOR FREE FIRST
The decision engine is deterministic Python + one Gemini call (free tier). So:
- Build and fully test discovery, classification, WhatsApp-trigger, and scheduling by feeding
  TYPED fake transcripts to the webhook locally. Zero phone calls. Zero paid minutes.
- Write unit tests (docs/03 has the test scenarios: hot, warm, cold, vague, callback).
- Get the brain 100% correct with text before making a SINGLE voice call.
- Only spend Vapi minutes on the FINAL voice integration, once the brain is proven.
Most people waste their whole trial debugging logic over live calls. Don't. Debug in a terminal.

## Testing discipline on real calls (every call-minute costs credit)
- Keep test calls SHORT and targeted: 60-90 seconds to check one behavior, then hang up.
- Don't ramble to "see how it goes" — script the specific path you're testing.
- Warm the Heroku dyno (`GET /health`) before each call so you don't pay for wake-up dead-air.
- Use a cheap/basic TTS voice, NOT a premium ElevenLabs voice (premium voice can cost more per
  minute than Vapi itself). Config the cheapest acceptable voice in Vapi.

## The safety switch — do this on day 1 in each dashboard
- **Vapi:** set a spending limit / turn off auto-recharge in the billing settings, so when the
  $10 trial ends it STOPS instead of silently charging the card.
- **Twilio (if used):** it's a trial by default; do not upgrade to paid unless forced.
- This is the actual protection against a surprise charge. Free trials require a card and will
  auto-bill the minute credits hit zero unless a limit is set.

## Do NOT do this
- **No multi-account trial farming.** It violates every provider's ToS, the card fingerprint gets
  flagged and accounts get suspended (possibly mid-evaluation-call), Twilio trial numbers can only
  call verified numbers anyway, and this assignment SCORES honesty/engineering judgment. Risking a
  frozen account to save ₹1,500 is a bad trade. Use the buffer instead.

## Realistic total spend
- Disciplined build (brain tested free, few short voice tests, one real eval call): **₹0-500.**
- With heavy voice testing overflow: up to the **₹1,500** cap.
- Keep every receipt — the assignment reimburses build/test costs when you join.
