import { useMemo, useState } from 'react';
import { paperBasename } from '../lib/api';
import { DataPanel } from '../components/DataPanel';

interface Paper {
  file_path: string;
  content_hash: string;
  created_at: number;
}

interface ArchiveViewProps {
  papers: Paper[];
  selectedPaper: string | null;
  onSelect: (path: string) => void;
  paperDetails: any;
  reviews: any;
  delibResult: any;
  appeals: any[];
  onRefreshAppeals: () => void;
}

function isTempPath(path: string): boolean {
  const n = path.replace(/\//g, '\\').toLowerCase();
  return n.includes('\\temp\\') || n.includes('\\appdata\\local\\temp');
}

export function ArchiveView({
  papers,
  selectedPaper,
  onSelect,
  paperDetails,
  reviews,
  delibResult,
  appeals,
  onRefreshAppeals,
}: ArchiveViewProps) {
  const [showTemp, setShowTemp] = useState(false);

  const visible = useMemo(
    () => (showTemp ? papers : papers.filter((p) => !isTempPath(p.file_path))),
    [papers, showTemp],
  );

  const hiddenCount = papers.length - visible.length;

  return (
    <div>
      <h1 className="view-title">Archive</h1>
      <p className="view-sub">Saved council runs from SQLite. Temp stress-test paths may no longer exist on disk.</p>
      <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8, marginBottom: 14, fontSize: '0.85rem' }}>
        <input
          type="checkbox"
          checked={showTemp}
          onChange={(e) => setShowTemp(e.target.checked)}
          data-testid="show-temp-toggle"
        />
        Show temp runs
        {!showTemp && hiddenCount > 0 ? (
          <span style={{ color: 'var(--muted)' }}>({hiddenCount} hidden)</span>
        ) : null}
      </label>
      <div className="council-grid">
        <div className="archive-list">
          {visible.length === 0 ? (
            <div className="panel-card" style={{ color: 'var(--muted)' }} data-testid="archive-empty">
              {papers.length === 0
                ? 'No papers yet.'
                : 'No non-temp papers. Toggle “Show temp runs” to see stress-test history.'}
            </div>
          ) : (
            visible.map((p) => (
              <button
                key={p.file_path}
                type="button"
                className={`archive-item${selectedPaper === p.file_path ? ' active' : ''}`}
                onClick={() => onSelect(p.file_path)}
              >
                <div className="name">{paperBasename(p.file_path)}</div>
                <div className="path">{new Date(p.created_at * 1000).toLocaleString()}</div>
              </button>
            ))
          )}
        </div>
        <div>
          {selectedPaper ? (
            <DataPanel
              aggregateScore={delibResult?.aggregate_score || 0}
              verdict={delibResult?.verdict || 'No verdict'}
              paperPath={selectedPaper}
              abstractText={paperDetails?.abstract}
              reportJson={delibResult?.report_json}
              reviews={reviews}
              appeals={appeals}
              onRefreshAppeals={onRefreshAppeals}
            />
          ) : (
            <div className="panel-card" style={{ color: 'var(--muted)' }}>Select a paper to inspect results.</div>
          )}
        </div>
      </div>
    </div>
  );
}
