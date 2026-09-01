'use client';

import useSWR from 'swr';
import Link from 'next/link';
import styles from './page.module.css';

const fetcher = (url: string) => fetch(url).then((res) => res.json());

export default function Dashboard() {
  // Poll every 2 seconds for new calls / state changes
  const { data: calls, error } = useSWR('/api/calls', fetcher, { refreshInterval: 2000 });

  if (error || calls?.error) return <div className={styles.container}>Failed to load calls: {calls?.error || 'Unknown Error'}</div>;
  if (!calls) return <div className={styles.container}>Initializing Telemetry...</div>;
  if (!Array.isArray(calls)) return <div className={styles.container}>Invalid data format</div>;

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <h1 className={styles.title}>ELEVATEBOX / TELEMETRY</h1>
        <p className={styles.subtitle}>ACTIVE CALL SESSIONS</p>
      </header>

      {calls.length === 0 ? (
        <div className={styles.emptyState}>[ NO ACTIVE SESSIONS DETECTED ]</div>
      ) : (
        <div className={styles.grid}>
          {calls.map((call: any) => (
            <Link href={`/${call.call_id}`} key={call.call_id} className={styles.card}>
              <div className={styles.cardHeader}>
                <div>
                  <div className={styles.callId}>{call.call_id.split('-')[0]}...</div>
                  <div className={styles.timestamp}>
                    {new Date(call.updated_at).toLocaleTimeString()}
                  </div>
                </div>
                <div className={`${styles.badge} ${styles[call.classification]}`}>
                  {call.classification}
                </div>
              </div>
              
              <div className={styles.details}>
                <div className={styles.detailRow}>
                  <span className={styles.label}>Language:</span>
                  <span className={styles.value}>{call.language || '--'}</span>
                </div>
                <div className={styles.detailRow}>
                  <span className={styles.label}>Confidence:</span>
                  <span className={styles.value}>{(call.confidence * 100).toFixed(0)}%</span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
