import React from 'react';

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
  if (!isApprovalRequired) return null;

  return (
    <div style={{ display: 'flex', gap: '10px', marginTop: '14px' }}>
      <button className="btn btn-primary" onClick={onApprove} data-testid="approve-btn">
        Approve Round {roundNum} and Continue
      </button>
      <button className="btn btn-danger" onClick={onAbort} data-testid="abort-btn">
        Abort Deliberation
      </button>
    </div>
  );
};
