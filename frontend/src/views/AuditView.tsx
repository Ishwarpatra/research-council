import { useEffect, useState, type ReactNode } from 'react';
import { API_BASE } from '../lib/api';

function renderNode(value: unknown, depth = 0): ReactNode {
  if (value == null) return <span style={{ color: 'var(--muted)' }}>null</span>;
  if (typeof value !== 'object') {
    return <span>{String(value)}</span>;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return <span style={{ color: 'var(--muted)' }}>[]</span>;
    return (
      <ul style={{ paddingLeft: 18, margin: '6px 0' }}>
        {value.map((item, i) => (
          <li key={i} style={{ marginBottom: 4 }}>
            {renderNode(item, depth + 1)}
          </li>
        ))}
      </ul>
    );
  }
  const entries = Object.entries(value as Record<string, unknown>);
  if (entries.length === 0) return <span style={{ color: 'var(--muted)' }}>{'{}'}</span>;
  if (depth >= 3) {
    return (
      <pre style={{ fontSize: '0.75rem', whiteSpace: 'pre-wrap', margin: 0 }}>
        {JSON.stringify(value, null, 2)}
      </pre>
    );
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {entries.map(([k, v]) => (
        <div key={k}>
          <div style={{ fontWeight: 600, fontSize: '0.82rem', marginBottom: 2 }}>{k}</div>
          <div style={{ fontSize: '0.82rem', color: 'var(--ink-soft)' }}>{renderNode(v, depth + 1)}</div>
        </div>
      ))}
    </div>
  );
}

export function AuditView() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/api/audit`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e: any) {
      setError(e?.message || 'Failed to load audit');
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div data-testid="audit-view">
      <h1 className="view-title">Audit</h1>
      <p className="view-sub">Monthly QA drift and skill-tree audit — from GET /api/audit.</p>
      <div style={{ marginBottom: 14 }}>
        <button type="button" className="btn btn-ghost" onClick={load} data-testid="audit-refresh">
          Refresh
        </button>
      </div>
      {loading ? <p style={{ color: 'var(--muted)' }}>Loading…</p> : null}
      {error ? (
        <div className="panel-card" style={{ color: 'var(--active)' }} data-testid="audit-error">
          {error}
        </div>
      ) : null}
      {!loading && !error && data ? (
        <div className="council-grid">
          <div className="panel-card" data-testid="audit-monthly">
            <h3 style={{ marginBottom: 10 }}>Monthly QA</h3>
            {renderNode(data.monthly)}
          </div>
          <div className="panel-card" data-testid="audit-skill-tree">
            <h3 style={{ marginBottom: 10 }}>Skill tree</h3>
            {renderNode(data.skill_tree)}
          </div>
        </div>
      ) : null}
    </div>
  );
}
