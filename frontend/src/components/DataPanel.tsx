import React from 'react';

interface DataPanelProps {
  aggregateScore: number;
  verdict: string;
  paperPath: string;
  abstractText?: string;
}

export const DataPanel: React.FC<DataPanelProps> = ({ aggregateScore, verdict, paperPath, abstractText }) => {
  const getScoreColor = (s: number) => {
    return s >= 4 ? '#22c55e' : s >= 3 ? '#f59e0b' : s >= 2 ? '#f97316' : '#ef4444';
  };

  return (
    <div className="data-panel" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div className="hitl-panel" style={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
        <div style={{
          width: '78px',
          height: '78px',
          borderRadius: '50%',
          border: `4px solid ${getScoreColor(aggregateScore)}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'column',
          flexShrink: 0
        }}>
          <span style={{ fontSize: '1.35rem', fontWeight: 700, color: getScoreColor(aggregateScore) }}>
            {aggregateScore.toFixed(2)}
          </span>
          <span style={{ fontSize: '.65rem', color: '#7a86a1' }}>/5.0</span>
        </div>
        <div>
          <h2 style={{ fontSize: '1.28rem', fontWeight: 700 }}>{verdict}</h2>
          <p style={{ fontSize: '0.72rem', color: '#7a86a1' }}>{paperPath}</p>
        </div>
      </div>

      {abstractText && (
        <div className="hitl-panel">
          <h3 style={{ fontSize: '0.85rem', color: '#7c6ff7', textTransform: 'uppercase', marginBottom: '10px' }}>Extracted Abstract</h3>
          <p style={{ fontSize: '0.8rem', color: '#7a86a1', lineHeight: 1.6 }}>{abstractText}</p>
        </div>
      )}
    </div>
  );
};
