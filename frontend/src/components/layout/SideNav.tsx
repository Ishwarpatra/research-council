import type { AppView } from '../../lib/api';

interface SideNavProps {
  view: AppView;
  onNavigate: (v: AppView) => void;
  sessionLabel: string;
  sessionSub: string;
  onNewExperiment: () => void;
  onLeavePortal?: () => void;
}

const ITEMS: { id: AppView; label: string }[] = [
  { id: 'research', label: 'Research' },
  { id: 'council', label: 'Council' },
  { id: 'archive', label: 'Archive' },
  { id: 'audit', label: 'Audit' },
  { id: 'lab', label: 'Lab' },
  { id: 'docs', label: 'Docs' },
];

export function SideNav({
  view,
  onNavigate,
  sessionLabel,
  sessionSub,
  onNewExperiment,
  onLeavePortal,
}: SideNavProps) {
  return (
    <aside className="side-nav">
      <div className="side-nav-header">
        <h2>{sessionLabel}</h2>
        <p>{sessionSub}</p>
      </div>
      <nav className="side-nav-menu" aria-label="Workspace">
        {ITEMS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`side-nav-item${view === item.id ? ' active' : ''}`}
            onClick={() => onNavigate(item.id)}
            data-testid={`side-${item.id}`}
          >
            <span className="side-nav-bullet" aria-hidden />
            <span>{item.label}</span>
          </button>
        ))}
      </nav>
      <div className="side-nav-footer">
        <button type="button" className="btn btn-primary" onClick={onNewExperiment} data-testid="new-experiment-btn">
          + New Experiment
        </button>
        <div className="side-nav-meta">
          <button type="button" data-testid="side-docs-footer" onClick={() => onNavigate('docs')}>
            Documentation
          </button>
          <button type="button" onClick={() => onNavigate('lab')}>
            System Status
          </button>
          {onLeavePortal ? (
            <button type="button" data-testid="leave-portal-btn" onClick={onLeavePortal}>
              Leave portal
            </button>
          ) : null}
        </div>
      </div>
    </aside>
  );
}
