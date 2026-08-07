import React from 'react';

interface AlertData {
  seq_id: number;
  state: string; // "Closed" | "Open" | "Half-Open"
  message: string;
}

interface ToastNotificationProps {
  alerts: AlertData[];
  onDismiss: (seqId: number) => void;
}

export const ToastNotification: React.FC<ToastNotificationProps> = ({ alerts, onDismiss }) => {
  if (alerts.length === 0) return null;

  const getAlertStyle = (state: string) => {
    switch (state) {
      case 'Open':
        return {
          background: 'rgba(239, 68, 68, 0.15)',
          border: '1px solid #ef4444',
          color: '#fca5a5',
          glow: '0 0 15px rgba(239, 68, 68, 0.35)'
        };
      case 'Half-Open':
        return {
          background: 'rgba(245, 158, 11, 0.15)',
          border: '1px solid #f59e0b',
          color: '#fde047',
          glow: '0 0 15px rgba(245, 158, 11, 0.35)'
        };
      case 'Closed':
      default:
        return {
          background: 'rgba(34, 197, 197, 0.15)',
          border: '1px solid #22c55e',
          color: '#86efac',
          glow: '0 0 15px rgba(34, 197, 94, 0.35)'
        };
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: '20px',
      right: '20px',
      zIndex: 9999,
      display: 'flex',
      flexDirection: 'column',
      gap: '10px',
      maxWidth: '380px'
    }}>
      {alerts.map((alert) => {
        const style = getAlertStyle(alert.state);
        return (
          <div
            key={alert.seq_id}
            data-testid={`toast-alert-${alert.seq_id}`}
            style={{
              background: style.background,
              border: style.border,
              boxShadow: style.glow,
              borderRadius: '8px',
              padding: '12px 16px',
              color: style.color,
              backdropFilter: 'blur(10px)',
              position: 'relative',
              animation: 'slideIn 0.3s ease-out',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <strong style={{ fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                ⚠️ Circuit Breaker: {alert.state}
              </strong>
              <button
                onClick={() => onDismiss(alert.seq_id)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'inherit',
                  cursor: 'pointer',
                  fontSize: '1rem',
                  lineHeight: 1,
                  padding: 0
                }}
                data-testid={`toast-close-${alert.seq_id}`}
              >
                &times;
              </button>
            </div>
            <p style={{ fontSize: '0.78rem', margin: 0, opacity: 0.95 }}>{alert.message}</p>
          </div>
        );
      })}
    </div>
  );
};
