import React, { useState, useEffect } from 'react';
import { API_BASE } from '../lib/api';
import { CircuitStatusChip } from './CircuitStatusChip';

interface SettingsPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export const SettingsPanel: React.FC<SettingsPanelProps> = ({ isOpen, onClose }) => {
  const [weights, setWeights] = useState<{ [key: string]: number }>({
    'Clarity & Presentation': 0.2,
    'Methodology Rigor': 0.25,
    'Novelty & Significance': 0.2,
    'Ethics & Integrity': 0.2,
    'Practical Impact': 0.15,
  });
  const [llmProvider, setLlmProvider] = useState<string>('stub');
  const [circuitStatus, setCircuitStatus] = useState<any>(null);
  const [saveStatus, setSaveStatus] = useState<string>('');
  const [errorMsg, setErrorMsg] = useState<string>('');

  useEffect(() => {
    if (isOpen) {
      loadSettings();
      loadCircuitHealth();
    }
  }, [isOpen]);

  const loadSettings = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/settings`);
      const data = await res.json();
      if (data.weights) setWeights(data.weights);
      if (data.llm_provider) setLlmProvider(data.llm_provider);
    } catch (err) {
      console.error('Failed to load settings:', err);
    }
  };

  const loadCircuitHealth = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/health/circuit`);
      setCircuitStatus(await res.json());
    } catch (err) {
      console.error('Failed to load circuit health:', err);
    }
  };

  const handleSliderChange = (criterion: string, val: number) => {
    setWeights((prev) => ({
      ...prev,
      [criterion]: Math.round(val * 100) / 100,
    }));
  };

  const totalSum = Object.values(weights).reduce((a, b) => a + b, 0);
  const isValidSum = Math.abs(totalSum - 1.0) <= 0.001;

  const saveSettings = async () => {
    if (!isValidSum) {
      setErrorMsg(`Weights must sum to 1.0 (current sum: ${totalSum.toFixed(2)})`);
      return;
    }
    setErrorMsg('');
    setSaveStatus('Saving...');
    try {
      const res = await fetch(`${API_BASE}/api/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ weights }),
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.error || 'Failed to save');
      }
      setSaveStatus('Saved successfully!');
      setTimeout(() => setSaveStatus(''), 2000);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to save settings');
      setSaveStatus('');
    }
  };

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0, 0, 0, 0.65)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        zIndex: 1000,
      }}
    >
      <div
        className="panel-card"
        style={{
          width: 520,
          maxWidth: '90vw',
          maxHeight: '90vh',
          overflow: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 18,
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            borderBottom: '1px solid var(--border)',
            paddingBottom: 12,
          }}
        >
          <h2 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--ink)' }}>System settings</h2>
          <button
            type="button"
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', color: 'var(--muted)', fontSize: '1.2rem', cursor: 'pointer' }}
          >
            x
          </button>
        </div>

        <CircuitStatusChip
          circuit={
            circuitStatus
              ? { ...circuitStatus, llm_provider: circuitStatus.llm_provider || llmProvider }
              : { llm_provider: llmProvider }
          }
          providerHint={llmProvider}
        />

        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <h3 style={{ fontSize: '0.85rem', textTransform: 'uppercase', color: 'var(--muted)', letterSpacing: '0.08em' }}>
              Consensus criteria weights
            </h3>
            <span style={{ fontSize: '0.78rem', fontWeight: 700, color: isValidSum ? 'var(--ok)' : 'var(--active)' }}>
              Total: {totalSum.toFixed(2)} / 1.00
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {Object.keys(weights).map((criterion) => (
              <div key={criterion} style={{ background: 'var(--surface-muted)', padding: '10px 14px', borderRadius: 10 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: 6 }}>
                  <span style={{ fontWeight: 500 }}>{criterion}</span>
                  <span style={{ color: 'var(--accent)', fontWeight: 700 }}>
                    {(weights[criterion] * 100).toFixed(0)}% ({weights[criterion].toFixed(2)})
                  </span>
                </div>
                <input
                  type="range"
                  min="0.05"
                  max="0.60"
                  step="0.01"
                  value={weights[criterion]}
                  onChange={(e) => handleSliderChange(criterion, parseFloat(e.target.value))}
                  style={{ width: '100%', accentColor: 'var(--accent)', cursor: 'pointer' }}
                />
              </div>
            ))}
          </div>
        </div>

        {errorMsg && (
          <div style={{ background: 'var(--active-bg)', border: '1px solid var(--active)', color: 'var(--active)', padding: '8px 12px', borderRadius: 8, fontSize: '0.78rem' }}>
            {errorMsg}
          </div>
        )}
        {saveStatus && (
          <div style={{ background: 'var(--ok-bg)', border: '1px solid var(--ok)', color: 'var(--ok)', padding: '8px 12px', borderRadius: 8, fontSize: '0.78rem' }}>
            {saveStatus}
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="btn btn-primary" onClick={saveSettings} disabled={!isValidSum}>
            Save weights
          </button>
        </div>
      </div>
    </div>
  );
};
