import { useState } from 'react';
import { API_BASE, paperBasename } from '../lib/api';

const FIXTURES = [
  { label: 'test_paper.txt', path: 'tests/fixtures/test_paper.txt' },
  { label: 'paper_grounded.txt', path: 'tests/fixtures/paper_grounded.txt' },
  { label: 'paper_ungrounded.txt', path: 'tests/fixtures/paper_ungrounded.txt' },
];

interface Paper {
  file_path: string;
  content_hash: string;
  created_at: number;
}

interface ResearchViewProps {
  paperPathInput: string;
  onPathChange: (v: string) => void;
  onStart: () => void;
  papers?: Paper[];
  statusMsg?: string;
  errorMsg?: string;
  starting?: boolean;
}

export function ResearchView({
  paperPathInput,
  onPathChange,
  onStart,
  papers = [],
  statusMsg,
  errorMsg,
  starting,
}: ResearchViewProps) {
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');

  const onFile = async (file: File | null) => {
    if (!file) return;
    setUploadError('');
    setUploading(true);
    try {
      const body = new FormData();
      body.append('file', file);
      const res = await fetch(`${API_BASE}/api/upload`, { method: 'POST', body });
      const data = await res.json().catch(() => ({}));
      const detail =
        typeof data.detail === 'string'
          ? data.detail
          : typeof data.error === 'string'
            ? data.error
            : '';
      if (!res.ok) {
        setUploadError(detail || `Upload failed (${res.status})`);
        return;
      }
      if (data.paper_path) onPathChange(data.paper_path);
    } catch {
      setUploadError('Upload failed — is the API on 8090?');
    } finally {
      setUploading(false);
    }
  };

  const recent = papers.slice(0, 8);

  return (
    <div>
      <h1 className="view-title">Research</h1>
      <p className="view-sub">
        Upload a manuscript, pick a recent archive paper, or enter a local path — then start deliberation.
      </p>
      <div className="panel-card">
        <div style={{ marginBottom: 14 }}>
          <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: 8 }}>
            Upload PDF / TXT / MD
          </label>
          <input
            type="file"
            accept=".pdf,.txt,.md,application/pdf,text/plain,text/markdown"
            data-testid="paper-file-input"
            disabled={!!uploading || !!starting}
            onChange={(e) => onFile(e.target.files?.[0] || null)}
          />
          {uploading ? (
            <p style={{ marginTop: 8, fontSize: '0.8rem', color: 'var(--muted)' }}>Uploading…</p>
          ) : null}
          {uploadError ? (
            <p data-testid="upload-error" style={{ marginTop: 8, fontSize: '0.85rem', color: 'var(--active)' }}>
              {uploadError}
            </p>
          ) : null}
        </div>

        {recent.length > 0 ? (
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: 8 }}>Recent papers</div>
            <div className="fixture-picks" style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {recent.map((p) => (
                <button
                  key={p.file_path}
                  type="button"
                  className="btn btn-ghost"
                  data-testid={`recent-${paperBasename(p.file_path)}`}
                  onClick={() => onPathChange(p.file_path)}
                  title={p.file_path}
                >
                  {paperBasename(p.file_path)}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        <div className="fixture-picks" style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 14 }}>
          {FIXTURES.map((f) => (
            <button
              key={f.path}
              type="button"
              className="btn btn-ghost"
              data-testid={`fixture-${f.label}`}
              onClick={() => onPathChange(f.path)}
            >
              {f.label}
            </button>
          ))}
        </div>
        <div className="form-row">
          <input
            type="text"
            placeholder="e.g. tests/fixtures/paper_grounded.txt"
            value={paperPathInput}
            onChange={(e) => onPathChange(e.target.value)}
            data-testid="paper-path-input"
          />
          <button
            type="button"
            className="btn btn-primary"
            onClick={onStart}
            disabled={!!starting || !!uploading}
            data-testid="start-deliberation-btn"
          >
            {starting ? 'Starting…' : 'Start deliberation'}
          </button>
        </div>
        {errorMsg ? (
          <p data-testid="research-error" style={{ marginTop: 12, fontSize: '0.85rem', color: 'var(--active)' }}>
            {errorMsg}
          </p>
        ) : null}
        {statusMsg ? (
          <p data-testid="research-status" style={{ marginTop: 12, fontSize: '0.85rem', color: 'var(--ok)' }}>
            {statusMsg}
          </p>
        ) : null}
        <p style={{ marginTop: 12, fontSize: '0.8rem', color: 'var(--muted)' }}>
          Uploads are stored under the API <code>uploads/</code> folder. Fixtures are relative to the API
          working directory. Only one deliberation may run at a time.
        </p>
      </div>
    </div>
  );
}
