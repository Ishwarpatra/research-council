import React, { useState } from 'react';

interface ApprovalControlsProps {
  isApprovalRequired: boolean;
  roundNum: number;
  onApprove: () => void;
  onAbort: () => void;
}

export const ApprovalControls: React.FC<ApprovalControlsProps> = ({
  isApprovalRequired,
  roundNum,
  onApprove,
  onAbort
}) => {
  const [confirmingAbort, setConfirmingAbort] = useState(false);

  if (!isApprovalRequired) return null;

  return (
    <div style={{ display: 'flex', gap: '10px', marginTop: '14px', alignItems: 'center' }}>
      <button className="btn btn-primary" onClick={onApprove} data-testid="approve-btn">
        Approve Round {roundNum} and Continue
      </button>

      {!confirmingAbort ? (
        <button className="btn btn-danger" onClick={() => setConfirmingAbort(true)} data-testid="abort-btn">
          Abort Deliberation
        </button>
      ) : (
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', background: 'rgba(239, 68, 68, 0.15)', padding: '4px 10px', borderRadius: '8px', border: '1px solid #ef4444' }}>
          <span style={{ fontSize: '0.75rem', color: '#ef4444', fontWeight: 600 }}>Confirm abort?</span>
          <button
            className="btn btn-danger"
            style={{ padding: '4px 10px', fontSize: '0.72rem' }}
            onClick={() => { setConfirmingAbort(false); onAbort(); }}
            data-testid="confirm-abort-btn"
          >
            Yes, Abort
          </button>
          <button
            className="btn"
            style={{ padding: '4px 10px', fontSize: '0.72rem', background: 'var(--surface-muted)', color: 'var(--ink)', border: '1px solid var(--border)' }}
            onClick={() => setConfirmingAbort(false)}
            data-testid="cancel-abort-btn"
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
};
