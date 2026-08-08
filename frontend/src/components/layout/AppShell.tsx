import type { AppView } from '../../lib/api';
import { TopNav } from './TopNav';
import { SideNav } from './SideNav';

interface AppShellProps {
  view: AppView;
  onNavigate: (v: AppView) => void;
  onOpenSettings: () => void;
  onNewExperiment: () => void;
  onLeavePortal?: () => void;
  sessionLabel: string;
  sessionSub: string;
  apiDown?: boolean;
  apiBase?: string;
  notificationSlot?: React.ReactNode;
  children: React.ReactNode;
}

export function AppShell({
  view,
  onNavigate,
  onOpenSettings,
  onNewExperiment,
  onLeavePortal,
  sessionLabel,
  sessionSub,
  apiDown,
  apiBase,
  notificationSlot,
  children,
}: AppShellProps) {
  return (
    <div className="app-shell">
      <TopNav
        onOpenSettings={onOpenSettings}
        notificationSlot={notificationSlot}
      />
      {apiDown ? (
        <div className="api-banner" data-testid="api-down-banner" role="alert">
          API unreachable at {apiBase || 'configured host'}. Start the stub server on port 8090, then refresh.
        </div>
      ) : null}
      <div className="app-body">
        <SideNav
          view={view}
          onNavigate={onNavigate}
          sessionLabel={sessionLabel}
          sessionSub={sessionSub}
          onNewExperiment={onNewExperiment}
          onLeavePortal={onLeavePortal}
        />
        <main className="app-main">{children}</main>
      </div>
    </div>
  );
}
