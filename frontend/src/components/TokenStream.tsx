import React from 'react';

interface TokenStreamProps {
  tokenBuffer: string;
}

export const TokenStream: React.FC<TokenStreamProps> = ({ tokenBuffer }) => {
  if (!tokenBuffer) return null;

  return (
    <div style={{ background: '#1e2235', padding: '12px', borderRadius: '10px', border: '1px solid #2b3050', marginBottom: '14px' }}>
      <h4 style={{ fontSize: '0.75rem', color: '#7a86a1', marginBottom: '6px' }}>Streaming Token Output (Live CoT):</h4>
      <pre style={{ fontSize: '0.75rem', fontFamily: 'monospace', whiteSpace: 'pre-wrap', color: '#e4e8f1', margin: 0 }}>{tokenBuffer}</pre>
    </div>
  );
};
