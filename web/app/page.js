'use client';

import { useState } from 'react';

export default function Home() {
  const [query, setQuery] = useState('');
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const askCPS = async () => {
    if (!query.trim()) return;

    setLoading(true);
    setAnswer('');
    setError('');

    try {
      const apiUrl =
        process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

      const response = await fetch(`${apiUrl}/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': 'dev_key_123',
        },
        body: JSON.stringify({
          query: query.trim(),
          use_cache: true,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || 'Something went wrong while contacting CPS Engine.'
        );
      }

      setAnswer(data.answer || 'Babu amsa.');
    } catch (err) {
      setError(err.message || 'An error occurred.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main
      style={{
        minHeight: '100vh',
        padding: '40px 20px',
        fontFamily: 'Arial, sans-serif',
        background: '#f5f7fb',
      }}
    >
      <div
        style={{
          maxWidth: '850px',
          margin: '0 auto',
        }}
      >
        <h1 style={{ fontSize: '42px', marginBottom: '10px' }}>
          CPS Engine
        </h1>

        <p style={{ fontSize: '18px', color: '#555' }}>
          Hausa History AI — Building Tomorrow's Intelligent Apps,
          One Prompt at a Time.
        </p>

        <div
          style={{
            marginTop: '40px',
            background: '#fff',
            padding: '25px',
            borderRadius: '16px',
            boxShadow: '0 4px 20px rgba(0,0,0,0.08)',
          }}
        >
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Tambayi CPS Engine game da tarihin Hausa..."
            rows={5}
            style={{
              width: '100%',
              padding: '15px',
              fontSize: '16px',
              borderRadius: '10px',
              border: '1px solid #ddd',
              resize: 'vertical',
              boxSizing: 'border-box',
            }}
          />

          <button
            onClick={askCPS}
            disabled={loading}
            style={{
              marginTop: '15px',
              padding: '13px 25px',
              border: 'none',
              borderRadius: '10px',
              background: '#111827',
              color: '#fff',
              fontSize: '16px',
              cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? '⏳ Ana tunani...' : '🤖 Tambaya'}
          </button>

          {error && (
            <div
              style={{
                marginTop: '20px',
                padding: '15px',
                borderRadius: '10px',
                background: '#fee2e2',
                color: '#991b1b',
              }}
            >
              ❌ {error}
            </div>
          )}

          {answer && (
            <div
              style={{
                marginTop: '25px',
                padding: '20px',
                borderRadius: '12px',
                background: '#f9fafb',
                lineHeight: '1.7',
              }}
            >
              <h2>🤖 Digital Mallam</h2>

              <p style={{ whiteSpace: 'pre-wrap' }}>
                {answer}
              </p>
            </div>
          )}
        </div>
      </div>
    </main>
  );
      }
