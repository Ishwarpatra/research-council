import React, { useState } from 'react';

export interface AlertData {
  seq_id: number;
  type?: string;
  state?: string;
  message?: string;
  round_num?: number;
  paper_path?: string;
  error?: string;
  report?: any;
}

interface ToastNotificationProps {
  alerts: AlertData[];
  onDismiss: (seqId: number) => void;
}

export const ToastNotification: React.FC<ToastNotificationProps> = ({ alerts, onDismiss }) => {
  if (alerts.length === 0) return null;

  const getAlertStyle = (alert: AlertData) => {
    if (alert.type === 'deliberation_completed' || alert.type === 'round_approved') {
      return {
        background: 'rgba(34, 197, 94, 0.18)',
        border: '1px solid #22c55e',
        color: '#86efac',
        title: alert.type === 'deliberation_completed' ? '✅ Deliberation Completed' : `👍 Round ${alert.round_num || ''} Approved`,
        msg: alert.report ? `Verdict: ${alert.report.executive_summary?.verdict}` : `Round ${alert.round_num || ''} approved by reviewer.`
      };
    }
    if (alert.type === 'deliberation_failed') {
      return {
        background: 'rgba(239, 68, 68, 0.18)',
        border: '1px solid #ef4444',
        color: '#fca5a5',
        title: '❌ Deliberation Failed',
        msg: alert.error || 'An error occurred during deliberation.'
      };
    }
    if (alert.type === 'deliberation_aborted') {
      return {
        background: 'rgba(245, 158, 11, 0.18)',
        border: '1px solid #f59e0b',
        color: '#fde047',
        title: '⚠️ Deliberation Aborted',
        msg: 'Deliberation session was cancelled by user.'
      };
    }

    // Default circuit breaker system alert
    switch (alert.state) {
      case 'Open':
        return {
          background: 'rgba(239, 68, 68, 0.18)',
          border: '1px solid #ef4444',
          color: '#fca5a5',
          title: `⚠️ Circuit Breaker: ${alert.state}`,
          msg: alert.message || ''
        };
      case 'Half-Open':
        return {
          background: 'rgba(245, 158, 11, 0.18)',
          border: '1px solid #f59e0b',
          color: '#fde047',
          title: `⚠️ Circuit Breaker: ${alert.state}`,
          msg: alert.message || ''
        };
      case 'Closed':
      default:
        return {
          background: 'rgba(34, 197, 94, 0.18)',
          border: '1px solid #22c55e',
          color: '#86efac',
          title: `ℹ️ Circuit Breaker: ${alert.state || 'Normal'}`,
          msg: alert.message || 'Circuit status operational.'
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
      {alerts.slice(-5).map((alert) => {
        const style = getAlertStyle(alert);
        return (
          <div
            key={alert.seq_id}
            data-testid={`toast-alert-${alert.seq_id}`}
            style={{
              background: style.background,
              border: style.border,
              borderRadius: '10px',
              padding: '12px 16px',
              color: style.color,
              backdropFilter: 'blur(10px)',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px',
              boxShadow: '0 8px 32px rgba(0,0,0,0.4)'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <strong style={{ fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                {style.title}
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
            <p style={{ fontSize: '0.78rem', margin: 0, opacity: 0.95 }}>{style.msg}</p>
          </div>
        );
      })}
    </div>
  );
};

export const NotificationBell: React.FC<{ alerts: AlertData[] }> = ({ alerts }) => {
  const [isOpen, setIsOpen] = useState(false);
  const unreadCount = alerts.length;

  return (
    <div style={{ position: 'relative' }}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          background: '#1e2235',
          border: '1px solid #2b3050',
          borderRadius: '20px',
          padding: '6px 12px',
          color: '#e4e8f1',
          fontSize: '0.8rem',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: '6px'
        }}
      >
        <span>🔔</span>
        <span>Notifications</span>
        {unreadCount > 0 && (
          <span style={{ background: '#7c6ff7', color: '#fff', borderRadius: '10px', padding: '1px 6px', fontSize: '0.68rem', fontWeight: 700 }}>
            {unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div style={{
          position: 'absolute', right: 0, top: '40px', width: '320px',
          background: '#151826', border: '1px solid #2b3050', borderRadius: '12px',
          padding: '12px', boxShadow: '0 8px 32px rgba(0,0,0,0.5)', zIndex: 1000
        }}>
          <h4 style={{ fontSize: '0.8rem', color: '#7c6ff7', textTransform: 'uppercase', marginBottom: '8px', borderBottom: '1px solid #2b3050', paddingBottom: '6px' }}>
            System Events History ({alerts.length})
          </h4>
          {alerts.length === 0 ? (
            <div style={{ fontSize: '0.75rem', color: '#7a86a1' }}>No events recorded.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '250px', overflowY: 'auto' }}>
              {alerts.slice(-10).reverse().map((a, i) => (
                <div key={i} style={{ background: '#1e2235', padding: '8px', borderRadius: '6px', fontSize: '0.72rem', color: '#7a86a1' }}>
                  <div style={{ color: '#e4e8f1', fontWeight: 600 }}>{a.type || a.state || 'Event'}</div>
                  <div>{a.message || a.error || (a.report ? `Verdict: ${a.report.executive_summary?.verdict}` : 'System notification')}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
