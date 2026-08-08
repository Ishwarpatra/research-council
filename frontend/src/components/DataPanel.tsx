import React, { useState } from 'react';
import { API_BASE, paperBasename } from '../lib/api';

interface ReviewItem {
  id?: number;
  agent_name?: string;
  agent?: string;
  criterion: string;
  score: number;
  justification?: string;
  evidence?: string[] | any;
  challenge_target?: string;
  round_num?: number;
}

interface DataPanelProps {
  aggregateScore: number;
  verdict: string;
  paperPath: string;
  abstractText?: string;
  reportJson?: any;
  reviews?: { rounds?: { [roundNum: string]: ReviewItem[] } } | any;
  appeals?: any[];
  onRefreshAppeals?: () => void;
}

export const DataPanel: React.FC<DataPanelProps> = ({
  aggregateScore,
  verdict,
  paperPath,
  abstractText,
  reportJson,
  reviews,
  appeals = [],
  onRefreshAppeals
}) => {
  const [rebuttalText, setRebuttalText] = useState("");
  const [isSubmittingAppeal, setIsSubmittingAppeal] = useState(false);
  const [appealMsg, setAppealMsg] = useState("");

  const getScoreColor = (s: number) => {
    return s >= 4 ? '#22c55e' : s >= 3 ? '#f59e0b' : s >= 2 ? '#f97316' : '#ef4444';
  };

  const getVerdictBadgeClass = (v: string) => {
    if (!v) return '';
    const l = v.toLowerCase();
    if (l === 'accept') return 'rgba(34,197,94,0.15)';
    if (l.includes('minor')) return 'rgba(245,158,11,0.15)';
    if (l.includes('major')) return 'rgba(249,115,22,0.15)';
    return 'rgba(239,68,68,0.15)';
  };

  const parsedReport = typeof reportJson === 'string' ? (() => {
    try { return JSON.parse(reportJson); } catch { return {}; }
  })() : (reportJson || {});

  const individualReviews: ReviewItem[] = parsedReport?.individual_reviews || [];
  const keyStrengths: string[] = parsedReport?.executive_summary?.key_strengths || [];
  const majorConcerns: string[] = parsedReport?.executive_summary?.major_concerns || [];
  const priorArtFindings: any[] = parsedReport?.prior_art_findings || [];

  const roundGroupedReviews: { [roundNum: string]: ReviewItem[] } = reviews?.rounds || {};
  const roundKeys = Object.keys(roundGroupedReviews).sort((a, b) => parseInt(a) - parseInt(b));

  const submitAppeal = async () => {
    if (!rebuttalText.trim()) {
      setAppealMsg("Please enter your rebuttal text.");
      return;
    }
    setIsSubmittingAppeal(true);
    setAppealMsg("Submitting appeal and re-deliberating...");
    try {
      const ep = encodeURIComponent(paperPath);
      const res = await fetch(`${API_BASE}/api/appeal?path=${ep}&rebuttal=${encodeURIComponent(rebuttalText)}`, {
        method: "POST"
      });
      const data = await res.json();
      if (res.ok) {
        setAppealMsg("Appeal submitted successfully! Verdict updated.");
        setRebuttalText("");
        if (onRefreshAppeals) onRefreshAppeals();
      } else {
        setAppealMsg("Appeal submission failed: " + (data.detail || data.error || "Unknown error"));
      }
    } catch (err: any) {
      setAppealMsg("Appeal failed: " + err.message);
    } finally {
      setIsSubmittingAppeal(false);
    }
  };

  return (
    <div className="data-panel" style={{ display: 'flex', flexDirection: 'column', gap: '20px', minWidth: 0, maxWidth: '100%' }}>
      {/* Top Header Card */}
      <div className="hitl-panel" style={{ display: 'flex', gap: '20px', alignItems: 'center', background: 'var(--surface)', border: '1px solid var(--border)', padding: '20px', borderRadius: '16px', minWidth: 0 }}>
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
          <span style={{ fontSize: '.65rem', color: 'var(--muted)' }}>/5.0</span>
        </div>
        <div>
          <h2 style={{ fontSize: '1.28rem', fontWeight: 700 }}>{verdict}</h2>
          <p style={{ fontSize: '0.72rem', color: 'var(--muted)' }}>{paperBasename(paperPath)}</p>
          <span style={{
            display: 'inline-block', marginTop: '6px', padding: '3px 10px', borderRadius: '12px',
            fontSize: '0.73rem', fontWeight: 600, background: getVerdictBadgeClass(verdict),
            color: getScoreColor(aggregateScore)
          }}>
            {verdict}
          </span>
        </div>
      </div>

      {/* Extracted Abstract */}
      {abstractText && (
        <div
          className="extracted-abstract"
          data-testid="extracted-abstract"
          style={{ background: 'var(--surface)', border: '1px solid var(--border)', padding: '16px', borderRadius: '12px', minWidth: 0, maxWidth: '100%', overflow: 'hidden' }}
        >
          <h3 style={{ fontSize: '0.82rem', color: 'var(--accent)', textTransform: 'uppercase', marginBottom: '8px', fontWeight: 700 }}>
            Extracted Abstract
          </h3>
          <p className="extracted-abstract-body">{abstractText}</p>
        </div>
      )}

      {/* Score Breakdown Grid */}
      <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', padding: '18px', borderRadius: '12px' }}>
        <h3 style={{ fontSize: '0.82rem', color: 'var(--accent)', textTransform: 'uppercase', marginBottom: '14px', fontWeight: 700 }}>
          Score Breakdown by Criterion
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '12px' }}>
          {individualReviews.length > 0 ? (
            individualReviews.map((r, i) => {
              const scorePct = Math.max(0, Math.min(100, ((r.score - 1) / 4 * 100)));
              const color = getScoreColor(r.score);
              return (
                <div key={i} style={{ background: 'var(--surface-muted)', border: '1px solid var(--border)', borderRadius: '10px', padding: '12px' }}>
                  <div style={{ fontSize: '0.72rem', color: 'var(--muted)', marginBottom: '4px' }}>{r.criterion}</div>
                  <div style={{ fontSize: '1.15rem', fontWeight: 700, color, marginBottom: '6px' }}>
                    {r.score.toFixed(1)} <span style={{ fontSize: '0.65rem', color: 'var(--muted)', fontWeight: 400 }}>/5.0</span>
                  </div>
                  <div style={{ background: 'var(--bg)', borderRadius: '4px', height: '6px', overflow: 'hidden' }}>
                    <div style={{ width: `${scorePct}%`, background: color, height: '100%', borderRadius: '4px', transition: 'width 0.5s' }} />
                  </div>
                  <div style={{ fontSize: '0.68rem', color: 'var(--muted)', marginTop: '6px' }}>
                    Agent: <span style={{ color: 'var(--ink)', fontWeight: 500 }}>{r.agent || r.agent_name}</span>
                  </div>
                </div>
              );
            })
          ) : (
            <div style={{ color: 'var(--muted)', fontSize: '0.8rem' }}>No individual score breakdown available.</div>
          )}
        </div>
      </div>

      {/* Executive Summary: Strengths & Concerns */}
      {(keyStrengths.length > 0 || majorConcerns.length > 0) && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', padding: '16px', borderRadius: '12px' }}>
            <h4 style={{ fontSize: '0.8rem', color: '#22c55e', textTransform: 'uppercase', marginBottom: '10px', fontWeight: 700 }}>
              Key Strengths
            </h4>
            <ul style={{ paddingLeft: '18px', fontSize: '0.78rem', color: 'var(--muted)', margin: 0, lineHeight: 1.6 }}>
              {keyStrengths.map((s, i) => <li key={i}>{s}</li>)}
            </ul>
          </div>
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', padding: '16px', borderRadius: '12px' }}>
            <h4 style={{ fontSize: '0.8rem', color: '#ef4444', textTransform: 'uppercase', marginBottom: '10px', fontWeight: 700 }}>
              Major Concerns
            </h4>
            <ul style={{ paddingLeft: '18px', fontSize: '0.78rem', color: 'var(--muted)', margin: 0, lineHeight: 1.6 }}>
              {majorConcerns.map((c, i) => <li key={i}>{c}</li>)}
            </ul>
          </div>
        </div>
      )}

      {/* Prior Art References */}
      {priorArtFindings.length > 0 && (
        <div style={{ background: 'var(--surface)', border: '1px solid var(--accent)', padding: '16px', borderRadius: '12px' }}>
          <h3 style={{ fontSize: '0.82rem', color: 'var(--accent)', textTransform: 'uppercase', marginBottom: '10px', fontWeight: 700 }}>
            Prior Art References (ChromaDB RAG)
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {priorArtFindings.map((item, i) => (
              <div key={i} style={{ background: 'var(--surface-muted)', padding: '10px 14px', borderRadius: '8px', fontSize: '0.78rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--ink)', fontWeight: 600, marginBottom: '4px' }}>
                  <span>Source: {item.source}</span>
                  <span style={{ color: 'var(--accent)' }}>Confidence: {(item.confidence_score * 100).toFixed(1)}%</span>
                </div>
                <div style={{ color: 'var(--muted)', lineHeight: 1.4 }}>{item.content}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Review Chain Timeline */}
      <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', padding: '18px', borderRadius: '12px' }}>
        <h3 style={{ fontSize: '0.82rem', color: 'var(--accent)', textTransform: 'uppercase', marginBottom: '14px', fontWeight: 700 }}>
          Deliberation Review Chain
        </h3>
        {roundKeys.length > 0 ? (
          roundKeys.map((rKey) => {
            const roundReviews = roundGroupedReviews[rKey];
            const roundTitle = rKey === '1' ? 'Round 1 - Initial Assessment' : rKey === '2' ? 'Round 2 - Peer Debate' : 'Round 3 - Final Positions';
            return (
              <div key={rKey} style={{ marginBottom: '18px' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--accent)', fontWeight: 700, textTransform: 'uppercase', marginBottom: '10px', borderBottom: '1px solid var(--border)', paddingBottom: '4px' }}>
                  {roundTitle}
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '10px' }}>
                  {roundReviews.map((rev, idx) => (
                    <div key={idx} style={{ background: 'var(--surface-muted)', border: '1px solid var(--border)', borderRadius: '10px', padding: '12px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                        <div>
                          <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--ink)' }}>{rev.agent_name}</div>
                          <div style={{ fontSize: '0.68rem', color: 'var(--muted)' }}>{rev.criterion}</div>
                        </div>
                        <span style={{ fontSize: '0.75rem', fontWeight: 700, padding: '2px 8px', borderRadius: '10px', background: 'var(--bg)', color: getScoreColor(rev.score) }}>
                          {rev.score.toFixed(1)}
                        </span>
                      </div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--muted)', lineHeight: 1.4, marginBottom: '6px' }}>
                        {rev.justification || 'No justification recorded.'}
                      </div>
                      {rev.challenge_target && (
                        <div style={{ fontSize: '0.68rem', color: '#f59e0b', background: 'rgba(245,158,11,0.1)', padding: '2px 6px', borderRadius: '4px' }}>
                          Challenging: {rev.challenge_target}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            );
          })
        ) : (
          <div style={{ color: 'var(--muted)', fontSize: '0.8rem' }}>No review chain timeline recorded for this paper.</div>
        )}
      </div>

      {/* Appeals Section & Author Rebuttal Form */}
      <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', padding: '18px', borderRadius: '12px' }}>
        <h3 style={{ fontSize: '0.82rem', color: 'var(--accent)', textTransform: 'uppercase', marginBottom: '14px', fontWeight: 700 }}>
          Author Appeals & Rebuttals
        </h3>

        {/* Prior Appeals List */}
        {appeals && appeals.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '16px' }}>
            {appeals.map((app) => (
              <div key={app.id} style={{ background: 'var(--surface-muted)', border: '1px solid var(--border)', padding: '12px', borderRadius: '8px', fontSize: '0.78rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span style={{ fontWeight: 600, color: 'var(--ink)' }}>Appeal #{app.id} Status: <span style={{ color: 'var(--accent)' }}>{app.status}</span></span>
                  <span style={{ color: '#22c55e', fontWeight: 700 }}>New Verdict: {app.new_verdict || 'Pending'}</span>
                </div>
                <div style={{ color: 'var(--muted)', fontStyle: 'italic' }}>Rebuttal: "{app.author_rebuttal}"</div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ fontSize: '0.78rem', color: 'var(--muted)', marginBottom: '14px' }}>No prior appeals recorded for this paper.</div>
        )}

        {/* New Rebuttal Form */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <textarea
            placeholder="Enter author rebuttal to submit an appeal and trigger re-deliberation..."
            value={rebuttalText}
            onChange={(e) => setRebuttalText(e.target.value)}
            rows={3}
            style={{
              background: 'var(--surface-muted)', border: '1px solid var(--border)', borderRadius: '8px',
              padding: '10px', color: 'var(--ink)', fontSize: '0.8rem', outline: 'none', resize: 'vertical'
            }}
          />
          {appealMsg && (
            <div style={{ fontSize: '0.75rem', color: appealMsg.includes('failed') ? '#ef4444' : '#22c55e' }}>
              {appealMsg}
            </div>
          )}
          <div>
            <button
              className="btn btn-primary"
              onClick={submitAppeal}
              disabled={isSubmittingAppeal}
              style={{ padding: '8px 16px', fontSize: '0.78rem' }}
            >
              {isSubmittingAppeal ? "Processing Appeal..." : "Submit Author Appeal"}
            </button>
          </div>
        </div>
      </div>

    </div>
  );
};
