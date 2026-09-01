# ElevateBox Telemetry Dashboard

Real-time call monitoring frontend for the ElevateBox voice agent. Reads live call state from the Turso Edge Database and streams transcript updates to the browser using Server-Sent Events.

Deployed at: https://elevatebox-telemetry.vercel.app

---

## What This Is

This is the visibility layer for the ElevateBox system. When a prospect is on a call with Priya (the voice agent), this dashboard shows:

- All active and recent call sessions
- Live transcript streaming, line by line, as the conversation happens
- Real-time lead classification: Hot, Warm, or Cold, with confidence percentage
- Extracted intelligence as it gets captured: budget, what they sell, product count, timeline, requested features
- System action status: whether WhatsApp was dispatched, whether a callback was booked

It does not control the voice agent. It only reads from the database.

---

## Architecture

The Next.js frontend connects directly to Turso (Edge SQLite). It does not proxy through the Python backend.

```
Turso Edge Database
  |
  v
Next.js API Routes (on Vercel)
  |-- GET /api/calls              polls all recent calls
  |-- GET /api/calls/:id          fetches one call's full state
  |-- GET /api/stream-call/:id    SSE stream: polls Turso every 1s, pushes transcript deltas
  |
  v
Browser (React)
  |-- Dashboard page: SWR polling every 2s for call grid
  |-- Call page: EventSource consuming the SSE stream
```

The SSE stream uses `ReadableStream` and `TextEncoder` natively. There is no dependency on the Vercel AI SDK because the AI generation happens on the Python backend, not here.

---

## Local Setup

Requires Node 20 or higher.

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:

```
TURSO_DATABASE_URL=libsql://your-db-name.turso.io
TURSO_AUTH_TOKEN=your_token_here
```

Run the dev server:

```bash
nvm use 20
npm run dev
```

Open http://localhost:3000.

---

## Deployment

Deployed on Vercel. Set root directory to `frontend` in Vercel project settings. Add `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` as environment variables. Every push to `master` on the main repository triggers a new deployment.

The frontend only needs the two Turso credentials. No Gemini, Vapi, or WhatsApp keys are needed or should be added here.
