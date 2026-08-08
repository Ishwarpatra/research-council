import { paperBasename } from '../lib/api';

interface SessionStatusBarProps {
  status: string;
  paperPath?: string | null;
  roundNum?: number;
  message?: string;
}

export function SessionStatusBar({ status, paperPath, roundNum, message }: SessionStatusBarProps) {
  const live = status === 'deliberating' || status === 'waiting_for_approval';
  const failed = status === 'failed';
  const aborted = status === 'aborted';
  const title = live
    ? 'Council in session'
    : status === 'completed'
      ? 'Council complete'
      : failed
        ? 'Council failed'
        : aborted
          ? 'Council aborted'
          : 'Council idle';
  const name = paperPath ? paperBasename(paperPath) : 'No manuscript';
  const msg =
    message ||
    (live
      ? `Orchestrator routing '${name}' — round ${roundNum || 1}`
      : status === 'completed'
        ? `Last session finished on '${name}'`
        : failed
          ? `Deliberation failed for '${name}'. Check Research for details or pick a .pdf/.txt file.`
          : aborted
            ? `Session cancelled for '${name}'. Start again from Research when ready.`
            : 'Start a deliberation from Research or New Experiment');
  const sid = paperPath
    ? `${paperBasename(paperPath).replace(/\W+/g, '').slice(0, 8) || 'sess'}-R${roundNum || 0}`
    : '—';

  return (
    <div className={`session-bar${failed || aborted ? ' session-bar-failed' : ''}`} data-testid="session-bar">
      <span className="session-pill">
        {live && <span className="dot" />}
        {title}
      </span>
      <span className="session-bar-msg">{msg}</span>
      <span className="session-bar-id">{sid}</span>
    </div>
  );
}
