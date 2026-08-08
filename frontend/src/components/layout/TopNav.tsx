interface TopNavProps {
  onOpenSettings: () => void;
  notificationSlot?: React.ReactNode;
}

export function TopNav({ onOpenSettings, notificationSlot }: TopNavProps) {
  return (
    <header className="top-nav">
      <div className="brand">Research Consensus Council</div>
      <div className="top-nav-actions">
        {notificationSlot}
        <button
          type="button"
          className="nav-action-btn"
          onClick={onOpenSettings}
          data-testid="settings-btn"
          aria-label="Settings"
          title="Settings"
        >
          Settings
        </button>
      </div>
    </header>
  );
}
