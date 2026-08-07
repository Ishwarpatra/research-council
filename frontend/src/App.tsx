import React, { useState, useEffect } from 'react';
import { useDeliberationStream } from './hooks/useDeliberationStream';

interface Paper {
  file_path: string;
  content_hash: string;
  created_at: number;
}

export default function App() {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [selectedPaper, setSelectedPaper] = useState<string | null>(null);
  const [paperDetails, setPaperDetails] = useState<any>(null);
  const [reviews, setReviews] = useState<any>(null);
  const [delibResult, setDelibResult] = useState<any>(null);
  
  // Input form
  const [paperPathInput, setPaperPathInput] = useState("");
  const [activePaperId, setActivePaperId] = useState<string>("");

  // Connect to the WebSocket token stream hook
  const { messages, liveTokenBuffer, readyState, isApprovalRequired } = useDeliberationStream(activePaperId);

  useEffect(() => {
    loadPapers();
  }, []);

  const loadPapers = async () => {
    try {
      const res = await fetch(`${import.meta.env.VITE_API_REST_URL || 'http://localhost:8080'}/api/papers`);
      const data = await res.json();
      setPapers(data);
    } catch (e) {
      console.error("Failed to load papers list", e);
    }
  };

  const selectPaper = async (path: string) => {
    setSelectedPaper(path);
    const ep = encodeURIComponent(path);
    try {
      const [detailsRes, reviewsRes, delibRes] = await Promise.all([
        fetch(`${import.meta.env.VITE_API_REST_URL || 'http://localhost:8080'}/api/paper?path=${ep}`),
        fetch(`${import.meta.env.VITE_API_REST_URL || 'http://localhost:8080'}/api/reviews?path=${ep}`),
        fetch(`${import.meta.env.VITE_API_REST_URL || 'http://localhost:8080'}/api/deliberation?path=${ep}`)
      ]);
      setPaperDetails(await detailsRes.json());
      setReviews(await reviewsRes.json());
      setDelibResult(await delibRes.json());
    } catch (e) {
      console.error("Failed to retrieve paper details", e);
    }
  };

  const startDeliberation = async () => {
    if (!paperPathInput.trim()) return alert("Enter a path.");
    try {
      const res = await fetch(`${import.meta.env.VITE_API_REST_URL || 'http://localhost:8080'}/api/deliberate?path=${encodeURIComponent(paperPathInput)}`, {
        method: "POST"
      });
      const data = await res.json();
      if (data.error) {
        alert("Error: " + data.error);
      } else {
        setActivePaperId(paperPathInput);
      }
    } catch (e) {
      alert("Failed to start deliberation.");
    }
  };

  const approveRound = async () => {
    try {
      await fetch(`${import.meta.env.VITE_API_REST_URL || 'http://localhost:8080'}/api/approve_round`, { method: "POST" });
    } catch (e) {
      console.error("Failed to approve round", e);
    }
  };

  const abortDeliberation = async () => {
    try {
      await fetch(`${import.meta.env.VITE_API_REST_URL || 'http://localhost:8080'}/api/abort_round`, { method: "POST" });
    } catch (e) {
      console.error("Failed to abort deliberation", e);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#0d0f1a', color: '#e4e8f1', fontFamily: 'system-ui' }}>
      <header style={{ background: 'linear-gradient(135deg, #1a1d35, #0d0f1a)', borderBottom: '1px solid #2b3050', padding: '14px 24px', display: 'flex', alignItems: 'center', gap: '14px' }}>
        <span style={{ fontSize: '1.25rem' }}>⚖️</span>
        <h1 style={{ fontSize: '1.05rem', fontWeight: 600 }}>Research Consensus Council Dashboard</h1>
        <span style={{ background: '#7c6ff7', color: '#fff', borderRadius: '20px', padding: '2px 9px', fontSize: '0.68rem', fontWeight: 700 }}>REACT Client</span>
      </header>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Left Sidebar: Processed Papers */}
        <aside style={{ width: '265px', background: '#151826', borderRight: '1px solid #2b3050', display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: '13px', borderBottom: '1px solid #2b3050' }}>
            <h2 style={{ fontSize: '0.69rem', textTransform: 'uppercase', letterSpacing: '0.11em', color: '#7a86a1', marginBottom: '8px' }}>Processed Papers</h2>
          </div>
          <div style={{ flex: 1, overflowY: 'auto', padding: '6px' }}>
            {papers.map((p) => (
              <div 
                key={p.file_path}
                onClick={() => selectPaper(p.file_path)}
                style={{
                  padding: '9px 11px',
                  borderRadius: '10px',
                  cursor: 'pointer',
                  marginBottom: '3px',
                  background: selectedPaper === p.file_path ? '#1e2235' : 'transparent',
                  border: selectedPaper === p.file_path ? '1px solid #7c6ff7' : '1px solid transparent'
                }}
              >
                <div style={{ fontSize: '0.81rem', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {p.file_path.split('/').pop()}
                </div>
                <div style={{ fontSize: '0.69rem', color: '#7a86a1', marginTop: '2px' }}>
                  {new Date(p.created_at * 1000).toLocaleDateString()}
                </div>
              </div>
            ))}
          </div>
        </aside>

        {/* Main Content Area */}
        <main style={{ flex: 1, overflowY: 'auto', padding: '22px 26px', background: '#0d0f1a' }}>
          
          {/* Active Deliberation / WebSocket Token Stream Panel */}
          {activePaperId && (
            <div className="hitl-panel" style={{ marginBottom: '20px', border: '1px solid #7c6ff7' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <h3 style={{ fontSize: '0.9rem', color: '#7c6ff7', textTransform: 'uppercase', fontWeight: 700 }}>Active Deliberation: {activePaperId.split('/').pop()}</h3>
                <span style={{ fontSize: '0.75rem', padding: '3px 9px', borderRadius: '12px', background: isApprovalRequired ? 'rgba(124,111,247,0.15)' : 'rgba(245,158,11,0.15)', color: isApprovalRequired ? '#7c6ff7' : '#f59e0b' }}>
                  {isApprovalRequired ? "Human Sign-off Required" : "Engine Processing..."}
                </span>
              </div>
              
              {/* Token Buffer Stream */}
              {liveTokenBuffer && (
                <div style={{ background: '#1e2235', padding: '12px', borderRadius: '10px', border: '1px solid #2b3050', marginBottom: '14px' }}>
                  <h4 style={{ fontSize: '0.75rem', color: '#7a86a1', marginBottom: '6px' }}>Streaming Token Output (Live CoT):</h4>
                  <pre style={{ fontSize: '0.75rem', fontFamily: 'monospace', whiteSpace: 'pre-wrap', color: '#e4e8f1' }}>{liveTokenBuffer}</pre>
                </div>
              )}

              {/* Action Pause sign-off controls */}
              {isApprovalRequired && (
                <div style={{ display: 'flex', gap: '10px', marginTop: '14px' }}>
                  <button className="btn btn-primary" onClick={approveRound}>Approve and Continue</button>
                  <button className="btn btn-danger" onClick={abortDeliberation}>Abort Deliberation</button>
                </div>
              )}
            </div>
          )}

          {/* Trigger Form */}
          <div style={{ background: '#151826', border: '1px solid #2b3050', borderRadius: '10px', padding: '14px', marginBottom: '20px' }}>
            <div style={{ display: 'flex', gap: '10px' }}>
              <input 
                type="text" 
                placeholder="Enter path to paper (e.g. tests/fixtures/test_paper.txt)" 
                value={paperPathInput}
                onChange={(e) => setPaperPathInput(e.target.value)}
                style={{ flex: 1, background: '#1e2235', border: '1px solid #2b3050', borderRadius: '10px', padding: '8px 12px', color: '#e4e8f1', outline: 'none' }}
              />
              <button className="btn btn-primary" onClick={startDeliberation}>Start Deliberation</button>
            </div>
          </div>

          {/* Selected Paper Details */}
          {selectedPaper ? (
            <div>
              <div className="hitl-panel" style={{ display: 'flex', gap: '20px', alignItems: 'center', marginBottom: '20px' }}>
                <div style={{ width: '78px', height: '78px', borderRadius: '50%', border: '4px solid #22c55e', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column' }}>
                  <span style={{ fontSize: '1.35rem', fontWeight: 700, color: '#22c55e' }}>
                    {delibResult?.aggregate_score?.toFixed(2) || '0.00'}
                  </span>
                </div>
                <div>
                  <h2 style={{ fontSize: '1.28rem', fontWeight: 700 }}>{delibResult?.verdict || 'Processing'}</h2>
                  <p style={{ fontSize: '0.72rem', color: '#7a86a1' }}>{selectedPaper}</p>
                </div>
              </div>

              {/* Sections summary */}
              {paperDetails && (
                <div className="hitl-panel" style={{ marginBottom: '20px' }}>
                  <h3 style={{ fontSize: '0.85rem', color: '#7c6ff7', textTransform: 'uppercase', marginBottom: '10px' }}>Extracted Abstract</h3>
                  <p style={{ fontSize: '0.8rem', color: '#7a86a1', lineHeight: 1.6 }}>{paperDetails.abstract}</p>
                </div>
              )}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '35vh', color: '#7a86a1', gap: '10px' }}>
              <div style={{ fontSize: '2.80rem', opacity: 0.22 }}>📋</div>
              <p>Select a paper to view its consensus results.</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
