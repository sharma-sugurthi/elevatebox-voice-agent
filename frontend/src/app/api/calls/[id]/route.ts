import { NextResponse } from 'next/server';
import { turso } from '@/lib/turso';

export const dynamic = 'force-dynamic';

export async function GET(request: Request, context: { params: Promise<{ id: string }> }) {
  try {
    const params = await context.params;
    const result = await turso.execute({
      sql: 'SELECT * FROM calls WHERE call_id = ?',
      args: [params.id],
    });

    if (result.rows.length === 0) {
      return NextResponse.json({ error: 'Call not found' }, { status: 404 });
    }

    const row = result.rows[0];
    const callState = {
      call_id: row.call_id,
      language: row.language,
      budget: row.budget,
      sells: row.sells,
      product_count: row.product_count,
      timeline: row.timeline,
      features: row.features ? JSON.parse(row.features as string) : [],
      classification: row.classification,
      confidence: row.confidence,
      barrier: row.barrier,
      whatsapp_sent: row.whatsapp_sent,
      callback_booked: row.callback_booked,
      transcript: row.transcript ? JSON.parse(row.transcript as string) : [],
      updated_at: row.updated_at,
    };

    return NextResponse.json(callState);
  } catch (error) {
    console.error('[API] Failed to fetch call:', error);
    return NextResponse.json({ error: 'Failed to fetch call' }, { status: 500 });
  }
}
