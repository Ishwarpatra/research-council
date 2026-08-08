import { SessionStatusBar } from '../components/SessionStatusBar';
import { AgentFlowBoard, type AgentRuntimeState } from '../components/AgentFlowBoard';
import { VerdictPanel } from '../components/VerdictPanel';
import { TokenStream } from '../components/TokenStream';
import { ApprovalControls } from '../components/ApprovalControls';
import { DataPanel } from '../components/DataPanel';

interface CouncilViewProps {
  activeStatus: string;
  activePath: string | null;
  activeRound: number;
  activeError?: string;
  paperDetails: any;
  reviews: any;
  delibResult: any;
  appeals: any[];
  agentStates: AgentRuntimeState[];
  liveTokenBuffer: string;
  isApprovalRequired: boolean;
  currentRoundNum: number;
  onApprove: () => void;
  onAbort: () => void;
  onRefreshAppeals: () => void;
  onStartResearch: () => void;
  selectedPaper: string | null;
  hitlError?: string;
  metrics: {
    agentsAligned: number;
    criticalFlags: number;
    quote: string | null;
    quoteAgent: string | null;
  };
}

export function CouncilView({
  activeStatus,
  activePath,
  activeRound,
  activeError,
  paperDetails,
  reviews,
  delibResult,
  appeals,
  agentStates,
  liveTokenBuffer,
  isApprovalRequired,
  currentRoundNum,
  onApprove,
  onAbort,
  onRefreshAppeals,
  onStartResearch,
  selectedPaper,
  hitlError,
  metrics,
}: CouncilViewProps) {
  const live = activeStatus === 'deliberating' || activeStatus === 'waiting_for_approval';
  const path = activePath || selectedPaper;
  const scored = agentStates.filter((a) => a.score != null);
  const liveAvg =
    scored.length > 0 ? scored.reduce((s, a) => s + (a.score as number), 0) / scored.length : 0;
  const score = delibResult?.aggregate_score || liveAvg || 0;
  const verdictLabel =
    delibResult?.verdict ||
    (activeStatus === 'aborted'
      ? 'Aborted'
      : activeStatus === 'failed'
        ? 'Failed'
        : live
          ? 'In progress'
          : 'No verdict');
  const idleEmpty =
    !live && !path && activeStatus !== 'completed' && activeStatus !== 'failed' && activeStatus !== 'aborted';

  return (
    <div>
      <SessionStatusBar
        status={activeStatus || 'idle'}
        paperPath={path}
        roundNum={activeRound || currentRoundNum}
        message={activeStatus === 'failed' ? (activeError || undefined) : undefined}
      />
      {activeStatus === 'failed' && activeError ? (
        <div className="panel-card" data-testid="council-fail-banner" style={{ marginBottom: 16, borderColor: 'var(--active)', color: 'var(--active)' }}>
          <strong>Deliberation failed.</strong> {activeError}
          <div style={{ marginTop: 10 }}>
            <button type="button" className="btn btn-primary" onClick={onStartResearch}>
              Pick a manuscript file
            </button>
          </div>
        </div>
      ) : null}
      {activeStatus === 'aborted' ? (
        <div className="panel-card" data-testid="council-abort-banner" style={{ marginBottom: 16, borderColor: 'var(--warn)', color: 'var(--warn)' }}>
          <strong>Deliberation aborted.</strong> Session was cancelled. Partial agent scores may still appear below.
          <div style={{ marginTop: 10 }}>
            <button type="button" className="btn btn-primary" onClick={onStartResearch}>
              Start again from Research
            </button>
          </div>
        </div>
      ) : null}
      {hitlError ? (
        <div className="panel-card" data-testid="council-hitl-error" style={{ marginBottom: 16, borderColor: 'var(--active)', color: 'var(--active)' }}>
          {hitlError}
        </div>
      ) : null}

      {idleEmpty ? (
        <div className="panel-card" data-testid="council-empty" style={{ textAlign: 'center', padding: 36 }}>
          <h2 className="view-title" style={{ fontSize: '1.35rem' }}>No active deliberation</h2>
          <p className="view-sub" style={{ marginBottom: 18 }}>
            Start from Research with a fixture path, then return here for live HITL and verdict.
          </p>
          <button type="button" className="btn btn-primary" data-testid="council-go-research" onClick={onStartResearch}>
            Start a deliberation
          </button>
        </div>
      ) : (
        <div className="council-grid">
          <div>
            <AgentFlowBoard
              paperPath={path}
              abstractText={paperDetails?.abstract}
              agentStates={agentStates}
            />

            {(activeStatus === 'waiting_for_approval' || (live && !!liveTokenBuffer)) && (
              <div className="hitl-panel">
                <TokenStream tokenBuffer={liveTokenBuffer} />
                <ApprovalControls
                  isApprovalRequired={isApprovalRequired && activeStatus === 'waiting_for_approval'}
                  roundNum={currentRoundNum}
                  onApprove={onApprove}
                  onAbort={onAbort}
                />
              </div>
            )}

            {selectedPaper && (
              <div style={{ marginTop: 16 }} data-testid="council-data-panel">
                <DataPanel
                  aggregateScore={delibResult?.aggregate_score || score}
                  verdict={verdictLabel === 'In progress' ? 'Processing' : verdictLabel}
                  paperPath={selectedPaper}
                  abstractText={paperDetails?.abstract}
                  reportJson={delibResult?.report_json}
                  reviews={reviews}
                  appeals={appeals}
                  onRefreshAppeals={onRefreshAppeals}
                />
              </div>
            )}
          </div>

          <VerdictPanel
            live={live}
            verdict={verdictLabel}
            aggregateScore={score}
            agentsAligned={metrics.agentsAligned}
            criticalFlags={metrics.criticalFlags}
            quote={metrics.quote}
            quoteAgent={metrics.quoteAgent}
            reportJson={delibResult?.report_json}
          />
        </div>
      )}
    </div>
  );
}
