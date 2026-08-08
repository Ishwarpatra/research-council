import React from 'react';

interface TokenStreamProps {
  tokenBuffer: string;
}

export const TokenStream: React.FC<TokenStreamProps> = ({ tokenBuffer }) => {
  if (!tokenBuffer) return null;

  return (
    <div
      style={{
        background: 'var(--surface-muted)',
        padding: '12px',
        borderRadius: '10px',
        border: '1px solid var(--border)',
        marginBottom: '14px',
      }}
    >
      <h4 style={{ fontSize: '0.75rem', color: 'var(--muted)', marginBottom: '6px' }}>
        Streaming token output (live CoT)
      </h4>
      <pre
        style={{
          fontSize: '0.75rem',
          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
          whiteSpace: 'pre-wrap',
          color: 'var(--ink)',
          margin: 0,
        }}
      >
        {tokenBuffer}
      </pre>
    </div>
  );
};
