import { useEffect, useState } from 'react';
import { API_BASE } from '../lib/api';
import { CircuitStatusChip } from '../components/CircuitStatusChip';

export function LabView() {
  const [circuit, setCircuit] = useState<any>(null);
  const [tools, setTools] = useState<any>(null);
  const [settings, setSettings] = useState<any>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [c, t, s] = await Promise.all([
          fetch(`${API_BASE}/api/health/circuit`),
          fetch(`${API_BASE}/api/skills/tools`),
          fetch(`${API_BASE}/api/settings`),
        ]);
        if (cancelled) return;
        setCircuit(await c.json());
        setTools(await t.json());
        setSettings(await s.json());
      } catch {
        if (!cancelled) setError('Could not reach API lab endpoints.');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div>
      <h1 className="view-title">Lab</h1>
      <p className="view-sub">System status, LLM circuit, and registered agent tools — live from the API.</p>
      {error ? <div className="panel-card" style={{ color: 'var(--active)' }}>{error}</div> : null}
      <div className="panel-card" style={{ marginBottom: 16 }}>
        <h3 style={{ marginBottom: 10 }}>Circuit breaker</h3>
        <CircuitStatusChip
          circuit={
            circuit
              ? { ...circuit, llm_provider: circuit.llm_provider || settings?.llm_provider }
              : settings
                ? { llm_provider: settings.llm_provider, fallback_provider: 'stub', status: 'UNKNOWN' }
                : null
          }
        />
      </div>
      <div className="panel-card" style={{ marginBottom: 16 }}>
        <h3 style={{ marginBottom: 10 }}>Settings snapshot</h3>
        <pre style={{ fontSize: '0.78rem', whiteSpace: 'pre-wrap' }} data-testid="lab-settings-raw">
          {settings
            ? JSON.stringify(
                {
                  llm_provider: settings.llm_provider,
                  weights: settings.weights,
                  retrieval_backend: settings.retrieval_backend,
                },
                null,
                2,
              )
            : 'Loading…'}
        </pre>
      </div>
      <div className="panel-card">
        <h3 style={{ marginBottom: 10 }}>Skill tools</h3>
        <ul style={{ paddingLeft: 18, fontSize: '0.88rem' }}>
          {(tools?.tools || []).map((name: string) => (
            <li key={name}>{name}</li>
          ))}
          {!tools && <li>Loading…</li>}
        </ul>
      </div>
    </div>
  );
}
