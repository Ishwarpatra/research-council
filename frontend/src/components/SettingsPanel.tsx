import React, { useState, useEffect } from 'react';

interface SettingsPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export const SettingsPanel: React.FC<SettingsPanelProps> = ({ isOpen, onClose }) => {
  const [weights, setWeights] = useState<{ [key: string]: number }>({
    "Clarity & Presentation": 0.20,
    "Methodology Rigor": 0.25,
    "Novelty & Significance": 0.20,
    "Ethics & Integrity": 0.20,
    "Practical Impact": 0.15,
  });
  const [llmProvider, setLlmProvider] = useState<string>("stub");
  const [circuitStatus, setCircuitStatus] = useState<any>(null);
  const [saveStatus, setSaveStatus] = useState<string>("");
  const [errorMsg, setErrorMsg] = useState<string>("");

  useEffect(() => {
    if (isOpen) {
      loadSettings();
      loadCircuitHealth();
    }
  }, [isOpen]);

  const loadSettings = async () => {
    try {
      const res = await fetch(`${import.meta.env.VITE_API_REST_URL || 'http://localhost:8080'}/api/settings`);
      const data = await res.json();
      if (data.weights) {
        setWeights(data.weights);
      }
      if (data.llm_provider) {
        setLlmProvider(data.llm_provider);
      }
    } catch (err) {
      console.error("Failed to load settings:", err);
    }
  };

  const loadCircuitHealth = async () => {
    try {
      const res = await fetch(`${import.meta.env.VITE_API_REST_URL || 'http://localhost:8080'}/api/health/circuit`);
      const data = await res.json();
      setCircuitStatus(data);
    } catch (err) {
      console.error("Failed to load circuit health:", err);
    }
  };

  const handleSliderChange = (criterion: string, val: number) => {
    setWeights(prev => ({
      ...prev,
      [criterion]: Math.round(val * 100) / 100
    }));
  };

  const totalSum = Object.values(weights).reduce((a, b) => a + b, 0);
  const isValidSum = Math.abs(totalSum - 1.0) <= 0.001;

  const saveSettings = async () => {
    if (!isValidSum) {
      setErrorMsg(`Weights must sum to 1.0 (current sum: ${totalSum.toFixed(2)})`);
      return;
    }
    setErrorMsg("");
    setSaveStatus("Saving...");
    try {
      const res = await fetch(`${import.meta.env.VITE_API_REST_URL || 'http://localhost:8080'}/api/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ weights })
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.error || "Failed to save");
      }
      setSaveStatus("Saved successfully!");
      setTimeout(() => setSaveStatus(""), 2000);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to save settings");
      setSaveStatus("");
    }
  };

  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(0, 0, 0, 0.7)', backdropFilter: 'blur(4px)',
      display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000
    }}>
      <div style={{
        background: '#151826', border: '1px solid #2b3050', borderRadius: '16px',
        width: '520px', maxWidth: '90vw', padding: '24px', boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
        color: '#e4e8f1', display: 'flex', flexDirection: 'column', gap: '18px'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #2b3050', paddingBottom: '12px' }}>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#7c6ff7' }}>⚙️ System Settings & Config</h2>
          <button
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', color: '#7a86a1', fontSize: '1.2rem', cursor: 'pointer' }}
          >
            ✕
          </button>
        </div>

        {/* LLM & Circuit Breaker Status */}
        <div style={{ background: '#1e2235', borderRadius: '10px', padding: '12px 16px', fontSize: '0.8rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontWeight: 600, color: '#e4e8f1' }}>Active Provider: <span style={{ color: '#7c6ff7' }}>{llmProvider}</span></div>
            <div style={{ fontSize: '0.72rem', color: '#7a86a1', marginTop: '2px' }}>
              Fallback: {circuitStatus?.fallback_provider || 'stub'}
            </div>
          </div>
          <div>
            <span style={{
              fontSize: '0.72rem', padding: '3px 8px', borderRadius: '12px', fontWeight: 600,
              background: circuitStatus?.status === 'CLOSED' ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)',
              color: circuitStatus?.status === 'CLOSED' ? '#22c55e' : '#ef4444'
            }}>
              Circuit: {circuitStatus?.status || 'UNKNOWN'}
            </span>
          </div>
        </div>

        {/* Criteria Weights Sliders */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <h3 style={{ fontSize: '0.85rem', textTransform: 'uppercase', color: '#7a86a1', letterSpacing: '0.08em' }}>
              Consensus Criteria Weights
            </h3>
            <span style={{
              fontSize: '0.78rem', fontWeight: 700,
              color: isValidSum ? '#22c55e' : '#ef4444'
            }}>
              Total: {totalSum.toFixed(2)} / 1.00
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {Object.keys(weights).map((criterion) => (
              <div key={criterion} style={{ background: '#1e2235', padding: '10px 14px', borderRadius: '10px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '6px' }}>
                  <span style={{ fontWeight: 500 }}>{criterion}</span>
                  <span style={{ color: '#7c6ff7', fontWeight: 700 }}>{(weights[criterion] * 100).toFixed(0)}% ({weights[criterion].toFixed(2)})</span>
                </div>
                <input
                  type="range"
                  min="0.05"
                  max="0.60"
                  step="0.01"
                  value={weights[criterion]}
                  onChange={(e) => handleSliderChange(criterion, parseFloat(e.target.value))}
                  style={{ width: '100%', accentColor: '#7c6ff7', cursor: 'pointer' }}
                />
              </div>
            ))}
          </div>
        </div>

        {errorMsg && (
          <div style={{ background: 'rgba(239,68,68,0.15)', border: '1px solid #ef4444', color: '#ef4444', padding: '8px 12px', borderRadius: '8px', fontSize: '0.78rem' }}>
            {errorMsg}
          </div>
        )}

        {saveStatus && (
          <div style={{ background: 'rgba(34,197,94,0.15)', border: '1px solid #22c55e', color: '#22c55e', padding: '8px 12px', borderRadius: '8px', fontSize: '0.78rem' }}>
            {saveStatus}
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '6px' }}>
          <button className="btn" style={{ background: '#2b3050', color: '#e4e8f1' }} onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={saveSettings} disabled={!isValidSum}>
            Save Weights
          </button>
        </div>
      </div>
    </div>
  );
};
