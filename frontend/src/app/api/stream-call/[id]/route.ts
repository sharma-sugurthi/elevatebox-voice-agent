import { turso } from '@/lib/turso';

export const dynamic = 'force-dynamic';
export const maxDuration = 300; // Allow long polling up to 5 minutes (Vercel max for Hobby is 10s, Pro is 300s, but we'll try)

export async function GET(request: Request, context: { params: Promise<{ id: string }> }) {
  const params = await context.params;
  // We use standard web streams to stream the transcript to the frontend.
  // This simulates the Vercel AI SDK DataStream for live viewing.
  const encoder = new TextEncoder();
  let lastTranscriptLength = 0;
  let isClosed = false;

  const stream = new ReadableStream({
    async start(controller) {
      controller.enqueue(encoder.encode(`data: {"type": "connected"}\n\n`));

      // Poll Turso every 1 second and stream new lines
      while (!isClosed) {
        try {
          const result = await turso.execute({
            sql: 'SELECT transcript, classification, confidence FROM calls WHERE call_id = ?',
            args: [params.id],
          });

          if (result.rows.length > 0) {
            const row = result.rows[0];
            const transcript = row.transcript ? JSON.parse(row.transcript as string) : [];
            
            // If there are new lines, stream them!
            if (transcript.length > lastTranscriptLength) {
              const newLines = transcript.slice(lastTranscriptLength);
              for (const line of newLines) {
                // Send standard SSE format
                controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'transcript', ...line })}\n\n`));
              }
              lastTranscriptLength = transcript.length;
              
              // Also stream classification updates
              controller.enqueue(encoder.encode(`data: ${JSON.stringify({ 
                type: 'state', 
                classification: row.classification,
                confidence: row.confidence
              })}\n\n`));
            }
          }
        } catch (e) {
          console.error('Polling error', e);
        }

        // Wait 1 second before polling again
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    },
    cancel() {
      isClosed = true;
    }
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      'Connection': 'keep-alive',
    },
  });
}
