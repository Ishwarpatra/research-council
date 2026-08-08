import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { DataPanel } from '../DataPanel';
import { TokenStream } from '../TokenStream';
import { ApprovalControls } from '../ApprovalControls';
import { ToastNotification } from '../ToastNotification';
import { TopNav } from '../layout/TopNav';
import { SideNav } from '../layout/SideNav';
import { VerdictPanel, formatTranscriptText } from '../VerdictPanel';
import { LandingView } from '../../views/LandingView';
import { ResearchView } from '../../views/ResearchView';
import { CouncilView } from '../../views/CouncilView';
import { ArchiveView } from '../../views/ArchiveView';
import { AuditView } from '../../views/AuditView';
import { DocsView } from '../../views/DocsView';

describe('DataPanel Component', () => {
  it('renders score, verdict and paper path correctly', () => {
    render(
      <DataPanel
        aggregateScore={4.5}
        verdict="Strong Accept"
        paperPath="tests/fixtures/test_paper.txt"
        abstractText="This is a test abstract."
      />
    );

    expect(screen.getByText('4.50')).toBeInTheDocument();
    expect(screen.getByText('/5.0')).toBeInTheDocument();
    expect(screen.getAllByText('Strong Accept').length).toBeGreaterThan(0);
    expect(screen.getByText('test_paper.txt')).toBeInTheDocument();
    expect(screen.getByText('This is a test abstract.')).toBeInTheDocument();
    expect(screen.getByTestId('extracted-abstract')).toBeInTheDocument();
  });

  it('applies wrap class on long unbroken abstract tokens', () => {
    const long = 'Makinglanguagemodelsbiggerdoesnotinherentlymakethembetteratfollowing';
    render(
      <DataPanel
        aggregateScore={3.5}
        verdict="Minor Revisions"
        paperPath="paper.pdf"
        abstractText={long}
      />
    );
    const body = screen.getByText(long);
    expect(body.className).toContain('extracted-abstract-body');
  });
});

describe('TokenStream Component', () => {
  it('renders token buffer if present', () => {
    render(<TokenStream tokenBuffer="thinking out loud..." />);
    expect(screen.getByText('thinking out loud...')).toBeInTheDocument();
  });

  it('renders nothing if token buffer is empty', () => {
    const { container } = render(<TokenStream tokenBuffer="" />);
    expect(container.firstChild).toBeNull();
  });
});

describe('ApprovalControls Component', () => {
  it('renders nothing when approval is not required', () => {
    const { container } = render(
      <ApprovalControls
        isApprovalRequired={false}
        roundNum={1}
        onApprove={() => {}}
        onAbort={() => {}}
      />
    );
    expect(container.firstChild).toBeNull();
  });

  it('calls handlers when approve or abort buttons are clicked', () => {
    const onApprove = vi.fn();
    const onAbort = vi.fn();

    render(
      <ApprovalControls
        isApprovalRequired={true}
        roundNum={2}
        onApprove={onApprove}
        onAbort={onAbort}
      />
    );

    expect(screen.getByText('Approve Round 2 and Continue')).toBeInTheDocument();
    expect(screen.getByText('Abort Deliberation')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('approve-btn'));
    expect(onApprove).toHaveBeenCalledTimes(1);

    // Abort button should toggle confirmation prompt first
    fireEvent.click(screen.getByTestId('abort-btn'));
    expect(screen.getByText('Confirm abort?')).toBeInTheDocument();
    
    fireEvent.click(screen.getByTestId('confirm-abort-btn'));
    expect(onAbort).toHaveBeenCalledTimes(1);
  });
});

describe('ToastNotification Component', () => {
  it('renders nothing when no alerts are present', () => {
    const { container } = render(<ToastNotification alerts={[]} onDismiss={() => {}} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders alerts with state-specific details and handles dismiss clicks', () => {
    const onDismiss = vi.fn();
    const mockAlerts = [
      {
        seq_id: 42,
        state: 'Open',
        message: 'Primary LLM failed. Tripped to OPEN.'
      },
      {
        seq_id: 43,
        state: 'Closed',
        message: 'LLM connection recovered. Closed.'
      }
    ];

    render(<ToastNotification alerts={mockAlerts} onDismiss={onDismiss} />);

    expect(screen.getByText('Circuit Breaker: Open')).toBeInTheDocument();
    expect(screen.getByText('Primary LLM failed. Tripped to OPEN.')).toBeInTheDocument();
    expect(screen.getByText('Circuit Breaker: Closed')).toBeInTheDocument();
    expect(screen.getByText('LLM connection recovered. Closed.')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('toast-close-42'));
    expect(onDismiss).toHaveBeenCalledWith(42);
  });
});

describe('TopNav', () => {
  it('shows settings and has no duplicate view links', () => {
    const onOpen = vi.fn();
    render(<TopNav onOpenSettings={onOpen} />);
    expect(screen.getByTestId('settings-btn')).toBeInTheDocument();
    expect(screen.queryByTestId('nav-council')).not.toBeInTheDocument();
    expect(screen.queryByTestId('nav-archive')).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId('settings-btn'));
    expect(onOpen).toHaveBeenCalled();
  });
});

describe('VerdictPanel', () => {
  it('shows synthesis metrics', () => {
    render(
      <VerdictPanel
        live
        verdict="Minor Revisions"
        aggregateScore={3.8}
        agentsAligned={3}
        criticalFlags={1}
        quote="Extrapolation beyond data."
        quoteAgent="Skeptical Reviewer"
      />
    );
    expect(screen.getByTestId('verdict-panel')).toBeInTheDocument();
    expect(screen.getByText('Synthesis Report')).toBeInTheDocument();
    expect(screen.getByText(/Extrapolation beyond data/)).toBeInTheDocument();
    expect(screen.getByText('Live')).toBeInTheDocument();
  });

  it('exports transcript as .txt plain text', () => {
    const blobs: Blob[] = [];
    const createObjectURL = vi.fn((blob: Blob) => {
      blobs.push(blob);
      return 'blob:mock';
    });
    const revokeObjectURL = vi.fn();
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL });
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

    const reportJson = {
      executive_summary: {
        verdict: 'Minor Revisions',
        aggregate_score: 3.8,
        key_strengths: ['Methodology Rigor: strong (4.5/5)'],
        major_concerns: ['Ethics & Integrity: weak (2.0/5)'],
      },
      individual_reviews: [
        {
          agent: 'Skeptical Reviewer',
          criterion: 'Clarity & Presentation',
          score: 3.5,
          justification: 'Extrapolation beyond data.',
        },
      ],
    };

    render(
      <VerdictPanel
        live={false}
        verdict="Minor Revisions"
        aggregateScore={3.8}
        reportJson={reportJson}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Export transcript' }));

    expect(click).toHaveBeenCalled();
    expect(createObjectURL).toHaveBeenCalled();
    const blob = blobs[0];
    expect(blob).toBeInstanceOf(Blob);
    expect(blob.type).toMatch(/^text\/plain/);
    const anchor = click.mock.instances[0] as unknown as HTMLAnchorElement;
    expect(anchor.download).toBe('rcc-transcript.txt');

    const text = formatTranscriptText(reportJson, { verdict: 'Minor Revisions', aggregateScore: 3.8 });
    expect(text).toContain('Research Consensus Council');
    expect(text).toContain('Verdict: Minor Revisions');
    expect(text.trimStart().startsWith('{')).toBe(false);

    click.mockRestore();
    vi.unstubAllGlobals();
  });
});

describe('LandingView', () => {
  it('renders brand and calls enter on Access Portal', () => {
    const onEnter = vi.fn();
    render(<LandingView onEnterPortal={onEnter} />);
    expect(screen.getByText('Research Consensus Council')).toBeInTheDocument();
    expect(screen.getByTestId('landing-hero-orbit')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('access-portal-btn'));
    expect(onEnter).toHaveBeenCalledWith('council');
    fireEvent.click(screen.getByTestId('start-validation-btn'));
    expect(onEnter).toHaveBeenCalledWith('research');
  });

  it('opens docs portal from Documentation', () => {
    const onEnter = vi.fn();
    render(<LandingView onEnterPortal={onEnter} />);
    fireEvent.click(screen.getByText('Documentation'));
    expect(onEnter).toHaveBeenCalledWith('docs');
  });
});

describe('ResearchView', () => {
  it('fills path from fixture quick-pick', () => {
    const onPathChange = vi.fn();
    render(
      <ResearchView paperPathInput="" onPathChange={onPathChange} onStart={() => {}} />
    );
    fireEvent.click(screen.getByTestId('fixture-paper_grounded.txt'));
    expect(onPathChange).toHaveBeenCalledWith('tests/fixtures/paper_grounded.txt');
  });

  it('exposes file upload control', () => {
    render(<ResearchView paperPathInput="" onPathChange={() => {}} onStart={() => {}} />);
    expect(screen.getByTestId('paper-file-input')).toBeInTheDocument();
  });

  it('picks a recent paper path', () => {
    const onPathChange = vi.fn();
    render(
      <ResearchView
        paperPathInput=""
        onPathChange={onPathChange}
        onStart={() => {}}
        papers={[
          { file_path: 'C:\\papers\\alpha.txt', content_hash: 'x', created_at: 1 },
        ]}
      />
    );
    fireEvent.click(screen.getByTestId('recent-alpha.txt'));
    expect(onPathChange).toHaveBeenCalledWith('C:\\papers\\alpha.txt');
  });
});

describe('SideNav', () => {
  it('is the workspace navigator for all views', () => {
    const onNavigate = vi.fn();
    render(
      <SideNav
        view="council"
        onNavigate={onNavigate}
        sessionLabel="RCC"
        sessionSub="test"
        onNewExperiment={() => {}}
        onLeavePortal={() => {}}
      />
    );
    expect(screen.getByTestId('side-council').className).toContain('active');
    for (const id of ['research', 'archive', 'audit', 'lab', 'docs'] as const) {
      fireEvent.click(screen.getByTestId(`side-${id}`));
      expect(onNavigate).toHaveBeenCalledWith(id);
    }
    expect(screen.getByTestId('leave-portal-btn')).toBeInTheDocument();
  });

  it('navigates to docs from Documentation footer', () => {
    const onNavigate = vi.fn();
    render(
      <SideNav
        view="research"
        onNavigate={onNavigate}
        sessionLabel="RCC"
        sessionSub="test"
        onNewExperiment={() => {}}
      />
    );
    fireEvent.click(screen.getByTestId('side-docs-footer'));
    expect(onNavigate).toHaveBeenCalledWith('docs');
    fireEvent.click(screen.getByTestId('side-audit'));
    expect(onNavigate).toHaveBeenCalledWith('audit');
  });
});

describe('CouncilView empty', () => {
  it('shows start CTA when idle with no paper', () => {
    const onStart = vi.fn();
    render(
      <CouncilView
        activeStatus="idle"
        activePath={null}
        activeRound={1}
        paperDetails={null}
        reviews={null}
        delibResult={null}
        appeals={[]}
        agentStates={[]}
        liveTokenBuffer=""
        isApprovalRequired={false}
        currentRoundNum={1}
        onApprove={() => {}}
        onAbort={() => {}}
        onRefreshAppeals={() => {}}
        onStartResearch={onStart}
        selectedPaper={null}
        metrics={{ agentsAligned: 0, criticalFlags: 0, quote: null, quoteAgent: null }}
      />
    );
    expect(screen.getByTestId('council-empty')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('council-go-research'));
    expect(onStart).toHaveBeenCalled();
  });

  it('shows failure banner when status is failed', () => {
    render(
      <CouncilView
        activeStatus="failed"
        activePath="C:\\tmp\\docs upload"
        activeRound={1}
        activeError="Path is a folder, not a manuscript file."
        paperDetails={null}
        reviews={null}
        delibResult={null}
        appeals={[]}
        agentStates={[]}
        liveTokenBuffer=""
        isApprovalRequired={false}
        currentRoundNum={1}
        onApprove={() => {}}
        onAbort={() => {}}
        onRefreshAppeals={() => {}}
        onStartResearch={() => {}}
        selectedPaper="C:\\tmp\\docs upload"
        metrics={{ agentsAligned: 0, criticalFlags: 0, quote: null, quoteAgent: null }}
      />
    );
    expect(screen.getByTestId('council-fail-banner')).toBeInTheDocument();
    expect(screen.getAllByText(/Path is a folder/).length).toBeGreaterThan(0);
  });

  it('shows DataPanel without collapsed details when paper selected', () => {
    render(
      <CouncilView
        activeStatus="completed"
        activePath="tests/fixtures/test_paper.txt"
        activeRound={1}
        paperDetails={{ abstract: 'Abs' }}
        reviews={null}
        delibResult={{ verdict: 'Accept', aggregate_score: 4.1 }}
        appeals={[]}
        agentStates={[]}
        liveTokenBuffer=""
        isApprovalRequired={false}
        currentRoundNum={1}
        onApprove={() => {}}
        onAbort={() => {}}
        onRefreshAppeals={() => {}}
        onStartResearch={() => {}}
        selectedPaper="tests/fixtures/test_paper.txt"
        metrics={{ agentsAligned: 0, criticalFlags: 0, quote: null, quoteAgent: null }}
      />
    );
    expect(screen.getByTestId('council-data-panel')).toBeInTheDocument();
    expect(screen.queryByTestId('full-report-details')).not.toBeInTheDocument();
  });
});

describe('AuditView', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        json: async () => ({ monthly: { ok: true }, skill_tree: { skills: [] } }),
      }))
    );
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('renders monthly and skill tree sections', async () => {
    render(<AuditView />);
    await waitFor(() => expect(screen.getByTestId('audit-monthly')).toBeInTheDocument());
    expect(screen.getByTestId('audit-skill-tree')).toBeInTheDocument();
  });
});

describe('DocsView', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        text: async () => '# ADK\nHello docs',
      }))
    );
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('loads ADK markdown body', async () => {
    render(<DocsView />);
    await waitFor(() => expect(screen.getByTestId('docs-body')).toBeInTheDocument());
    expect(screen.getByTestId('docs-body').textContent).toContain('Hello docs');
  });
});

describe('ArchiveView temp filter', () => {
  it('hides temp paths by default', () => {
    const papers = [
      { file_path: 'tests/fixtures/test_paper.txt', content_hash: 'a', created_at: 1 },
      { file_path: 'C:\\Users\\x\\AppData\\Local\\Temp\\paper_0.txt', content_hash: 'b', created_at: 2 },
    ];
    render(
      <ArchiveView
        papers={papers}
        selectedPaper={null}
        onSelect={() => {}}
        paperDetails={null}
        reviews={null}
        delibResult={null}
        appeals={[]}
        onRefreshAppeals={() => {}}
      />
    );
    expect(screen.getByText('test_paper.txt')).toBeInTheDocument();
    expect(screen.queryByText('paper_0.txt')).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId('show-temp-toggle'));
    expect(screen.getByText('paper_0.txt')).toBeInTheDocument();
  });
});
