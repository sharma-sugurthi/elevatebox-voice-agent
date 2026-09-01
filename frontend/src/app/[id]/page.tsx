'use client';

import React, { useEffect, useState, useRef } from 'react';
import Link from 'next/link';
import styles from './call.module.css';

export default function LiveCall({ params }: { params: Promise<{ id: string }> }) {
  const unwrappedParams = React.use(params);
  const [transcript, setTranscript] = useState<any[]>([]);
  const [state, setState] = useState<any>({
    classification: 'cold',
    confidence: 0,
    language: '--',
    budget: null,
    sells: null,
    product_count: null,
    timeline: null,
    features: [],
    whatsapp_sent: 0,
    callback_booked: null,
  });
  
  const [isConnected, setIsConnected] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Initial fetch to get full state
    fetch(`/api/calls/${unwrappedParams.id}`)
      .then(res => res.json())
      .then(data => {
        if (!data.error) {
          setState(data);
          setTranscript(data.transcript || []);
        }
      });

    // Open SSE for live streaming updates
    const eventSource = new EventSource(`/api/stream-call/${unwrappedParams.id}`);
    
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'connected') {
        setIsConnected(true);
      } else if (data.type === 'transcript') {
        setTranscript(prev => {
          // Prevent duplicates by checking if we already have this exact line
          // (Since SSE just sends new lines, but we might have fetched them in the initial load)
          const exists = prev.some(t => t.content === data.content && t.role === data.role);
          if (exists) return prev;
          return [...prev, { role: data.role, content: data.content }];
        });
      } else if (data.type === 'state') {
        setState((prev: any) => ({
          ...prev,
          classification: data.classification,
          confidence: data.confidence,
        }));
      }
    };

    return () => {
      eventSource.close();
    };
  }, [unwrappedParams.id]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript]);

  return (
    <div className={styles.layout}>
      {/* LEFT PANE: TRANSCRIPT */}
      <div className={styles.transcriptPane}>
        <div className={styles.header}>
          <div className={styles.title}>LIVE STREAM: {unwrappedParams.id}</div>
          <div className={styles.subtitle}>
            STATUS: {isConnected ? 'CONNECTED' : 'CONNECTING...'}
            <span style={{ marginLeft: 16 }}>
              <Link href="/" style={{ color: 'var(--text-secondary)' }}>&larr; BACK TO GRID</Link>
            </span>
          </div>
        </div>
        
        <div className={styles.messages}>
          {transcript.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
              [ WAITING FOR TRANSMISSION ]
            </div>
          ) : (
            transcript.map((msg, i) => (
              <div key={i} className={`${styles.message} ${msg.role === 'user' ? styles.messageUser : styles.messageAssistant}`}>
                <div className={styles.messageRole}>{msg.role}</div>
                <div className={styles.messageContent}>{msg.content}</div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* RIGHT PANE: TELEMETRY */}
      <div className={styles.telemetryPane}>
        <div className={styles.section}>
          <div className={styles.sectionTitle}>Live Classification</div>
          <div className={`${styles.badge} ${styles[state.classification]}`}>
            {state.classification} [{(state.confidence * 100).toFixed(0)}%]
          </div>
        </div>

        <div className={styles.section}>
          <div className={styles.sectionTitle}>Extracted Intelligence</div>
          
          <div className={styles.dataRow}>
            <span className={styles.dataLabel}>Language Detection</span>
            <span className={`${styles.dataValue} ${!state.language ? styles.null : ''}`}>
              {state.language || 'Awaiting'}
            </span>
          </div>

          <div className={styles.dataRow}>
            <span className={styles.dataLabel}>Budget Constraint</span>
            <span className={`${styles.dataValue} ${!state.budget ? styles.null : ''}`}>
              {state.budget || 'NULL'}
            </span>
          </div>

          <div className={styles.dataRow}>
            <span className={styles.dataLabel}>Product Sells</span>
            <span className={`${styles.dataValue} ${!state.sells ? styles.null : ''}`}>
              {state.sells || 'NULL'}
            </span>
          </div>

          <div className={styles.dataRow}>
            <span className={styles.dataLabel}>Timeline</span>
            <span className={`${styles.dataValue} ${!state.timeline ? styles.null : ''}`}>
              {state.timeline || 'NULL'}
            </span>
          </div>

          <div className={styles.dataRow}>
            <span className={styles.dataLabel}>Product Count</span>
            <span className={`${styles.dataValue} ${!state.product_count ? styles.null : ''}`}>
              {state.product_count || 'NULL'}
            </span>
          </div>
        </div>

        {state.features?.length > 0 && (
          <div className={styles.section}>
            <div className={styles.sectionTitle}>Requested Features</div>
            <div className={styles.featuresList}>
              {state.features.map((f: string, i: number) => (
                <div key={i} className={styles.featureItem}>+ {f}</div>
              ))}
            </div>
          </div>
        )}

        <div className={styles.section}>
          <div className={styles.sectionTitle}>System Actions</div>
          <div className={styles.dataRow}>
            <span className={styles.dataLabel}>WhatsApp Dispatched</span>
            <span className={styles.dataValue}>{state.whatsapp_sent ? 'TRUE' : 'FALSE'}</span>
          </div>
          <div className={styles.dataRow}>
            <span className={styles.dataLabel}>Callback Booked</span>
            <span className={`${styles.dataValue} ${!state.callback_booked ? styles.null : ''}`}>
              {state.callback_booked ? new Date(state.callback_booked).toLocaleString() : 'FALSE'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
