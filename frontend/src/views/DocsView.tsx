import { useEffect, useState } from 'react';

export function DocsView() {
  const [text, setText] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch('/ADK.md');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const body = await res.text();
        if (!cancelled) {
          setText(body);
          setError('');
        }
      } catch (e: any) {
        if (!cancelled) setError(e?.message || 'Failed to load ADK.md');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div data-testid="docs-view">
      <h1 className="view-title">Documentation</h1>
      <p className="view-sub">Agent Development Kit (ADK) — as-built system contract for RCC.</p>
      {loading ? <p style={{ color: 'var(--muted)' }}>Loading…</p> : null}
      {error ? (
        <div className="panel-card" style={{ color: 'var(--active)' }} data-testid="docs-error">
          Could not load docs: {error}
        </div>
      ) : null}
      {!loading && !error ? (
        <pre
          className="panel-card"
          data-testid="docs-body"
          style={{
            whiteSpace: 'pre-wrap',
            fontSize: '0.82rem',
            lineHeight: 1.55,
            maxHeight: '70vh',
            overflow: 'auto',
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
          }}
        >
          {text}
        </pre>
      ) : null}
    </div>
  );
}
