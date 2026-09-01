import { NextResponse } from 'next/server';
import { turso } from '@/lib/turso';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const result = await turso.execute(`
      SELECT call_id, classification, confidence, updated_at, language, budget, sells, product_count, timeline, features, whatsapp_sent, callback_booked
      FROM calls
      ORDER BY updated_at DESC
      LIMIT 50
    `);

    const calls = result.rows.map((row) => ({
      call_id: row.call_id,
      classification: row.classification,
      confidence: row.confidence,
      updated_at: row.updated_at,
      language: row.language,
      budget: row.budget,
      sells: row.sells,
      product_count: row.product_count,
      timeline: row.timeline,
      features: row.features ? JSON.parse(row.features as string) : [],
      whatsapp_sent: row.whatsapp_sent,
      callback_booked: row.callback_booked,
    }));

    return NextResponse.json(calls);
  } catch (error) {
    console.error('[API] Failed to fetch calls:', error);
    return NextResponse.json({ error: 'Failed to fetch calls' }, { status: 500 });
  }
}
