interface CircuitStatusChipProps {
  circuit: {
    status?: string;
    primary_failures?: number;
    llm_provider?: string;
    fallback_provider?: string;
  } | null;
  providerHint?: string;
}

export function CircuitStatusChip({ circuit, providerHint }: CircuitStatusChipProps) {
  const status = (circuit?.status || 'UNKNOWN').toUpperCase();
  const closed = status === 'CLOSED';
  const failures = circuit?.primary_failures ?? 0;
  const provider = circuit?.llm_provider || providerHint || '—';
  const fallback = circuit?.fallback_provider || 'stub';

  return (
    <div
      className="circuit-status-chip"
      data-testid="circuit-status-chip"
      style={{
        background: 'var(--surface-muted)',
        borderRadius: 10,
        padding: '12px 16px',
        fontSize: '0.8rem',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: 12,
      }}
    >
      <div>
        <div style={{ fontWeight: 600 }}>
          Active provider: <span style={{ color: 'var(--accent)' }}>{provider}</span>
        </div>
        <div style={{ fontSize: '0.72rem', color: 'var(--muted)', marginTop: 2 }}>
          Fallback: {fallback}
          {failures > 0 ? ` · primary failures: ${failures}` : ''}
        </div>
        {providerHint !== undefined ? (
          <div style={{ fontSize: '0.72rem', color: 'var(--muted)', marginTop: 4 }}>
            Change provider via <code>.env</code> (<code>LLM_PROVIDER</code>) and restart the API.
          </div>
        ) : null}
      </div>
      <span
        style={{
          fontSize: '0.72rem',
          padding: '3px 8px',
          borderRadius: 12,
          fontWeight: 600,
          whiteSpace: 'nowrap',
          background: closed ? 'var(--ok-bg)' : 'var(--active-bg)',
          color: closed ? 'var(--ok)' : 'var(--active)',
        }}
      >
        Circuit: {status}
      </span>
    </div>
  );
}
