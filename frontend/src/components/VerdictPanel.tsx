interface VerdictPanelProps {
  live: boolean;
  verdict?: string;
  aggregateScore?: number;
  agentsAligned?: number;
  agentsTotal?: number;
  criticalFlags?: number;
  quote?: string | null;
  quoteAgent?: string | null;
  reportJson?: unknown;
  onExport?: () => void;
}

function consensusLabel(score: number): string {
  if (score >= 4.5) return 'High';
  if (score >= 3.5) return 'Moderate';
  if (score >= 2.5) return 'Low';
  return 'Poor';
}

type ReportLike = {
  executive_summary?: {
    verdict?: string;
    aggregate_score?: number;
    key_strengths?: string[];
    major_concerns?: string[];
  };
  individual_reviews?: Array<{
    agent?: string;
    criterion?: string;
    score?: number;
    justification?: string;
    challenge_target?: string;
  }>;
  actionable_feedback?: {
    prioritized_revisions?: string[];
    decision_path?: string;
  };
};

function asReport(raw: unknown): ReportLike | null {
  if (typeof raw === 'string') {
    try {
      return JSON.parse(raw) as ReportLike;
    } catch {
      return null;
    }
  }
  if (!raw || typeof raw !== 'object') return null;
  return raw as ReportLike;
}

/** Format council report (or verdict/score fallback) as plain-text transcript. */
export function formatTranscriptText(
  reportJson: unknown,
  fallback: { verdict: string; aggregateScore: number },
): string {
  const report = asReport(reportJson);
  const summary = report?.executive_summary;
  const verdict = summary?.verdict ?? fallback.verdict;
  const score = summary?.aggregate_score ?? fallback.aggregateScore;
  const lines: string[] = [
    'Research Consensus Council — Transcript',
    '',
    `Verdict: ${verdict}`,
    `Aggregate score: ${(Number(score) || 0).toFixed(2)}`,
  ];

  const strengths = summary?.key_strengths ?? [];
  if (strengths.length) {
    lines.push('', 'Key strengths');
    for (const s of strengths) lines.push(`- ${s}`);
  }

  const concerns = summary?.major_concerns ?? [];
  if (concerns.length) {
    lines.push('', 'Major concerns');
    for (const c of concerns) lines.push(`- ${c}`);
  }

  const reviews = report?.individual_reviews ?? [];
  if (reviews.length) {
    lines.push('', 'Individual reviews');
    for (const r of reviews) {
      lines.push('---');
      lines.push(`Agent: ${r.agent ?? 'Unknown'}`);
      lines.push(`Criterion: ${r.criterion ?? '—'}`);
      lines.push(`Score: ${r.score != null ? `${r.score}/5` : '—'}`);
      if (r.justification) lines.push(`Justification: ${r.justification}`);
      if (r.challenge_target) lines.push(`Challenge: ${r.challenge_target}`);
    }
  }

  const feedback = report?.actionable_feedback;
  const revisions = feedback?.prioritized_revisions ?? [];
  if (revisions.length) {
    lines.push('', 'Prioritized revisions');
    for (const r of revisions) lines.push(`- ${r}`);
  }
  if (feedback?.decision_path) {
    lines.push('', `Decision path: ${feedback.decision_path}`);
  }

  return lines.join('\n') + '\n';
}

export function VerdictPanel({
  live,
  verdict = 'Pending',
  aggregateScore = 0,
  agentsAligned = 0,
  agentsTotal = 5,
  criticalFlags = 0,
  quote,
  quoteAgent,
  reportJson,
  onExport,
}: VerdictPanelProps) {
  const exportTranscript = () => {
    if (onExport) return onExport();
    const text = formatTranscriptText(reportJson, { verdict, aggregateScore });
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'rcc-transcript.txt';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <aside className="panel-card verdict-panel" data-testid="verdict-panel">
      <div className="head">
        <span className="eyebrow">Verdict</span>
        {live ? <span className="live-badge">Live</span> : null}
      </div>
      <h2>Synthesis Report</h2>
      <div className="metric-row">
        <span className="label">Consensus</span>
        <span>
          <span style={{ color: aggregateScore >= 3.5 ? 'var(--ok)' : 'var(--warn)' }}>● </span>
          {consensusLabel(aggregateScore)} ({(aggregateScore || 0).toFixed(2)})
        </span>
      </div>
      <div className="metric-row">
        <span className="label">Agents aligned</span>
        <span>
          {agentsAligned}/{agentsTotal}
        </span>
      </div>
      <div className="metric-row">
        <span className="label">Critical flags</span>
        <span style={{ color: criticalFlags > 0 ? 'var(--active)' : 'var(--ink)' }}>{criticalFlags}</span>
      </div>
      <div className="metric-row">
        <span className="label">Decision</span>
        <span>{verdict || 'Pending'}</span>
      </div>
      {quote ? (
        <div className="quote-box">
          “{quote}”
          {quoteAgent ? <cite>— {quoteAgent}</cite> : null}
        </div>
      ) : (
        <div className="quote-box" style={{ background: 'var(--surface-muted)', color: 'var(--ink-soft)' }}>
          No challenge callout yet. Reviews will appear here as the council runs.
        </div>
      )}
      <button type="button" className="btn btn-primary" style={{ width: '100%', marginTop: 16 }} onClick={exportTranscript}>
        Export transcript
      </button>
    </aside>
  );
}
