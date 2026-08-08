import { useState, useEffect, useMemo, useRef } from 'react';
import { useDeliberationStream } from './hooks/useDeliberationStream';
import { ToastNotification, NotificationBell } from './components/ToastNotification';
import { SettingsPanel } from './components/SettingsPanel';
import { AppShell } from './components/layout/AppShell';
import { CouncilView } from './views/CouncilView';
import { ResearchView } from './views/ResearchView';
import { ArchiveView } from './views/ArchiveView';
import { LabView } from './views/LabView';
import { DocsView } from './views/DocsView';
import { AuditView } from './views/AuditView';
import { LandingView } from './views/LandingView';
import { API_BASE, paperBasename, type AppView } from './lib/api';
import { COUNCIL_AGENTS, type AgentStatus } from './lib/agents';
import type { AgentRuntimeState } from './components/AgentFlowBoard';

const PORTAL_KEY = 'rcc_portal';

interface Paper {
  file_path: string;
  content_hash: string;
  created_at: number;
}

interface ActiveDeliberation {
  status?: string;
  paper_path?: string | null;
  round_num?: number;
  reviews?: any[];
  error_message?: string;
}

function readPortalFlag(): boolean {
  try {
    return sessionStorage.getItem(PORTAL_KEY) === '1';
  } catch {
    return false;
  }
}

export default function App() {
  const [portalOpen, setPortalOpen] = useState(readPortalFlag);
  const [view, setView] = useState<AppView>('council');
  const [papers, setPapers] = useState<Paper[]>([]);
  const [selectedPaper, setSelectedPaper] = useState<string | null>(null);
  const [paperDetails, setPaperDetails] = useState<any>(null);
  const [reviews, setReviews] = useState<any>(null);
  const [delibResult, setDelibResult] = useState<any>(null);
  const [appeals, setAppeals] = useState<any[]>([]);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [paperPathInput, setPaperPathInput] = useState('');
  const [activePaperId, setActivePaperId] = useState('');
  const [active, setActive] = useState<ActiveDeliberation>({ status: 'idle' });
  const [apiDown, setApiDown] = useState(false);
  const [researchError, setResearchError] = useState('');
  const [researchStatus, setResearchStatus] = useState('');
  const [starting, setStarting] = useState(false);
  const prevStatus = useRef<string | undefined>(undefined);

  const { liveTokenBuffer, isApprovalRequired, currentRoundNum, systemAlerts, dismissAlert } =
    useDeliberationStream(portalOpen ? activePaperId : '');

  useEffect(() => {
    const onPop = (e: PopStateEvent) => {
      const inPortal = Boolean(e.state && (e.state as { rccPortal?: boolean }).rccPortal);
      if (inPortal) {
        try {
          sessionStorage.setItem(PORTAL_KEY, '1');
        } catch {
          /* ignore */
        }
        setPortalOpen(true);
      } else {
        try {
          sessionStorage.removeItem(PORTAL_KEY);
        } catch {
          /* ignore */
        }
        setActivePaperId('');
        setPortalOpen(false);
      }
    };
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  // Refresh while portal is open: mark current history entry so Forward/Back stay coherent.
  useEffect(() => {
    if (!portalOpen) return;
    const st = window.history.state as { rccPortal?: boolean } | null;
    if (!st?.rccPortal) {
      window.history.replaceState({ rccPortal: true }, '');
    }
  }, [portalOpen]);

  const enterPortal = (next?: AppView) => {
    try {
      sessionStorage.setItem(PORTAL_KEY, '1');
    } catch {
      /* ignore */
    }
    if (next) setView(next);
    setPortalOpen(true);
    const st = window.history.state as { rccPortal?: boolean } | null;
    if (!st?.rccPortal) {
      window.history.pushState({ rccPortal: true }, '');
    }
  };

  const leavePortal = () => {
    try {
      sessionStorage.removeItem(PORTAL_KEY);
    } catch {
      /* ignore */
    }
    setActivePaperId('');
    setPortalOpen(false);
    const st = window.history.state as { rccPortal?: boolean } | null;
    if (st?.rccPortal) {
      window.history.back();
    }
  };

  useEffect(() => {
    if (!portalOpen) return;
    loadPapers();
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/settings`);
        setApiDown(!res.ok);
      } catch {
        setApiDown(true);
      }
    })();
  }, [portalOpen]);

  useEffect(() => {
    if (!portalOpen) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/active_deliberation`);
        if (!res.ok) {
          if (!cancelled) setApiDown(true);
          return;
        }
        const data = await res.json();
        if (!cancelled) {
          setApiDown(false);
          setActive(data || { status: 'idle' });
        }
      } catch {
        if (!cancelled) setApiDown(true);
      }
    };
    tick();
    const id = window.setInterval(tick, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [portalOpen]);

  useEffect(() => {
    if (!portalOpen) return;
    if (active?.paper_path && (active.status === 'deliberating' || active.status === 'waiting_for_approval')) {
      setActivePaperId(active.paper_path);
      if (!selectedPaper) {
        selectPaper(active.paper_path);
      }
    }
  }, [portalOpen, active?.paper_path, active?.status]);

  useEffect(() => {
    if (!portalOpen) return;
    const status = active?.status;
    const path = active?.paper_path;
    if (prevStatus.current && prevStatus.current !== 'completed' && status === 'completed' && path) {
      selectPaper(path);
      loadPapers();
      setResearchStatus('Deliberation completed — verdict refreshed.');
    }
    prevStatus.current = status;
  }, [portalOpen, active?.status, active?.paper_path]);

  useEffect(() => {
    const done = systemAlerts.find((a) => a.type === 'deliberation_completed');
    if (done?.paper_path) {
      selectPaper(done.paper_path);
      loadPapers();
    }
  }, [systemAlerts]);

  const loadPapers = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/papers`);
      if (!res.ok) throw new Error('papers');
      setPapers(await res.json());
      setApiDown(false);
    } catch (e) {
      console.error('Failed to load papers list', e);
      setApiDown(true);
    }
  };

  const selectPaper = async (path: string) => {
    setSelectedPaper(path);
    const ep = encodeURIComponent(path);
    try {
      const [detailsRes, reviewsRes, delibRes, appealsRes] = await Promise.all([
        fetch(`${API_BASE}/api/paper?path=${ep}`),
        fetch(`${API_BASE}/api/reviews?path=${ep}`),
        fetch(`${API_BASE}/api/deliberation?path=${ep}`),
        fetch(`${API_BASE}/api/appeals?path=${ep}`).catch(() => ({ json: async () => [] }) as Response),
      ]);
      setPaperDetails(detailsRes.ok ? await detailsRes.json() : null);
      setReviews(reviewsRes.ok ? await reviewsRes.json() : null);
      setDelibResult(delibRes.ok ? await delibRes.json() : null);
      setAppeals(appealsRes.ok ? await appealsRes.json() : []);
    } catch (e) {
      console.error('Failed to retrieve paper details', e);
    }
  };

  const refreshAppeals = async () => {
    if (!selectedPaper) return;
    const ep = encodeURIComponent(selectedPaper);
    try {
      const [delibRes, appealsRes] = await Promise.all([
        fetch(`${API_BASE}/api/deliberation?path=${ep}`),
        fetch(`${API_BASE}/api/appeals?path=${ep}`),
      ]);
      setDelibResult(await delibRes.json());
      setAppeals(await appealsRes.json());
    } catch (e) {
      console.error('Failed to refresh appeals', e);
    }
  };

  const startDeliberation = async () => {
    setResearchError('');
    setResearchStatus('');
    if (!paperPathInput.trim()) {
      setResearchError('Enter a manuscript path (or pick a fixture).');
      return;
    }
    setStarting(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/deliberate?path=${encodeURIComponent(paperPathInput)}`,
        { method: 'POST' },
      );
      const data = await res.json().catch(() => ({}));
      const detail =
        typeof data.detail === 'string'
          ? data.detail
          : Array.isArray(data.detail)
            ? data.detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ')
            : data.error || '';
      if (!res.ok || data.error) {
        setResearchError(detail || `Request failed (${res.status})`);
        setApiDown(res.status >= 500);
      } else {
        const path = paperPathInput.trim();
        setActivePaperId(path);
        await selectPaper(path);
        setView('council');
        setResearchStatus('Deliberation started — watching Council.');
        loadPapers();
      }
    } catch {
      setResearchError('Failed to reach API. Is the server on 8090?');
      setApiDown(true);
    } finally {
      setStarting(false);
    }
  };

  const approveRound = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/approve_round`, { method: 'POST' });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setResearchStatus('');
        setResearchError(body.error || body.detail || `Approve failed (${res.status})`);
      } else {
        setResearchError('');
        setResearchStatus(`Round ${currentRoundNum} approved — continuing deliberation.`);
      }
    } catch (e) {
      console.error('Failed to approve round', e);
      setResearchError('Failed to reach API to approve round.');
    }
  };

  const abortDeliberation = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/abort_round`, { method: 'POST' });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setResearchError(body.error || body.detail || `Abort failed (${res.status})`);
      } else {
        setResearchError('');
        setResearchStatus('Deliberation abort requested.');
      }
    } catch (e) {
      console.error('Failed to abort deliberation', e);
      setResearchError('Failed to reach API to abort.');
    }
  };

  const agentStates: AgentRuntimeState[] = useMemo(() => {
    const liveReviews: any[] = active?.reviews || [];
    const rounds = reviews?.rounds || {};
    const roundKeys = Object.keys(rounds).sort((a, b) => parseInt(a, 10) - parseInt(b, 10));
    const latestRound = roundKeys.length ? rounds[roundKeys[roundKeys.length - 1]] : [];
    const archived: any[] = Array.isArray(latestRound) ? latestRound : [];
    const live = active?.status === 'deliberating' || active?.status === 'waiting_for_approval';

    return COUNCIL_AGENTS.map((agent) => {
      const fromLive = liveReviews.find((r) => r.agent_name === agent.name || r.agent === agent.name);
      const fromArch = archived.find((r) => r.agent_name === agent.name || r.agent === agent.name);
      const hit = fromLive || fromArch;
      let status: AgentStatus = 'awaiting';
      if (hit) status = 'done';
      else if (live && liveTokenBuffer) status = 'reviewing';
      if (live && hit?.challenge_target) status = 'active';
      else if (live && !hit && liveTokenBuffer && agent.name === 'Skeptical Reviewer') status = 'active';
      return {
        name: agent.name,
        status,
        challenge: hit?.challenge_target || null,
        score: hit?.score ?? null,
        justification: hit?.justification || null,
      };
    });
  }, [active, reviews, liveTokenBuffer]);

  const metrics = useMemo(() => {
    const parsed =
      typeof delibResult?.report_json === 'string'
        ? (() => {
            try {
              return JSON.parse(delibResult.report_json);
            } catch {
              return {};
            }
          })()
        : delibResult?.report_json || {};
    const individuals: any[] = parsed?.individual_reviews || [];
    const score = delibResult?.aggregate_score || 0;
    const agentsAligned = individuals.filter((r) => Math.abs((r.score || 0) - score) <= 0.75).length;
    const criticalFlags = individuals.filter((r) => (r.score || 5) < 2.5 || r.challenge_target).length;
    const challenger =
      individuals.find((r) => r.challenge_target) ||
      agentStates.find((a) => a.challenge || (a.justification && a.status === 'active'));
    const quote =
      challenger?.justification ||
      parsed?.executive_summary?.major_concerns?.[0] ||
      null;
    const quoteAgent = challenger?.agent || challenger?.agent_name || challenger?.name || null;
    return { agentsAligned, criticalFlags, quote, quoteAgent };
  }, [delibResult, agentStates]);

  const sessionLabel = 'RCC Lab';
  const sessionSub = active?.paper_path
    ? `Active: ${paperBasename(active.paper_path)} · ${active.status || 'idle'}`
    : 'No active session';

  if (!portalOpen) {
    return <LandingView onEnterPortal={enterPortal} />;
  }

  return (
    <>
      <AppShell
        view={view}
        onNavigate={setView}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onNewExperiment={() => setView('research')}
        onLeavePortal={leavePortal}
        sessionLabel={sessionLabel}
        sessionSub={sessionSub}
        apiDown={apiDown}
        apiBase={API_BASE}
        notificationSlot={<NotificationBell alerts={systemAlerts} />}
      >
        {view === 'council' && (
          <CouncilView
            activeStatus={active?.status || 'idle'}
            activePath={active?.paper_path || null}
            activeRound={active?.round_num || currentRoundNum}
            activeError={active?.error_message || ''}
            paperDetails={paperDetails}
            reviews={reviews}
            delibResult={delibResult}
            appeals={appeals}
            agentStates={agentStates}
            liveTokenBuffer={liveTokenBuffer}
            isApprovalRequired={isApprovalRequired}
            currentRoundNum={currentRoundNum}
            onApprove={approveRound}
            onAbort={abortDeliberation}
            onRefreshAppeals={refreshAppeals}
            onStartResearch={() => setView('research')}
            selectedPaper={selectedPaper}
            hitlError={researchError}
            metrics={metrics}
          />
        )}
        {view === 'research' && (
          <ResearchView
            paperPathInput={paperPathInput}
            onPathChange={(v) => {
              setPaperPathInput(v);
              setResearchError('');
            }}
            onStart={startDeliberation}
            papers={papers}
            errorMsg={researchError}
            statusMsg={researchStatus}
            starting={starting}
          />
        )}
        {view === 'archive' && (
          <ArchiveView
            papers={papers}
            selectedPaper={selectedPaper}
            onSelect={(path) => {
              selectPaper(path);
            }}
            paperDetails={paperDetails}
            reviews={reviews}
            delibResult={delibResult}
            appeals={appeals}
            onRefreshAppeals={refreshAppeals}
          />
        )}
        {view === 'lab' && <LabView />}
        {view === 'audit' && <AuditView />}
        {view === 'docs' && <DocsView />}
      </AppShell>
      <ToastNotification alerts={systemAlerts} onDismiss={dismissAlert} />
      <SettingsPanel isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
    </>
  );
}
