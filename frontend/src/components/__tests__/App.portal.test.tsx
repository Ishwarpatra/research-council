import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import App from '../../App';

function mockFetchOk() {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      let body: unknown = {};
      if (url.includes('/api/papers')) body = [];
      if (url.includes('/api/settings')) body = { weights: {}, db_path: 'council.db' };
      if (url.includes('/api/active_deliberation')) body = { status: 'idle' };
      return {
        ok: true,
        json: async () => body,
      } as Response;
    })
  );
}

describe('App portal history', () => {
  beforeEach(() => {
    sessionStorage.clear();
    window.history.replaceState(null, '', '/');
    mockFetchOk();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    sessionStorage.clear();
  });

  it('pushes history on enter and returns to landing on popstate', async () => {
    render(<App />);
    expect(screen.getByTestId('access-portal-btn')).toBeInTheDocument();

    const lenBefore = window.history.length;
    fireEvent.click(screen.getByTestId('access-portal-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('side-council')).toBeInTheDocument();
    });
    expect(window.history.state).toEqual({ rccPortal: true });
    expect(window.history.length).toBeGreaterThanOrEqual(lenBefore);
    expect(sessionStorage.getItem('rcc_portal')).toBe('1');

    act(() => {
      window.history.back();
    });
    // jsdom may not fire popstate on history.back — dispatch explicitly if still in portal
    if (screen.queryByTestId('side-council')) {
      act(() => {
        window.dispatchEvent(new PopStateEvent('popstate', { state: null }));
      });
    }

    await waitFor(() => {
      expect(screen.getByTestId('access-portal-btn')).toBeInTheDocument();
    });
    expect(sessionStorage.getItem('rcc_portal')).toBeNull();
  });

  it('Leave portal returns to landing', async () => {
    render(<App />);
    fireEvent.click(screen.getByTestId('start-validation-btn'));
    await waitFor(() => {
      expect(screen.getByTestId('side-research')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('leave-portal-btn'));
    await waitFor(() => {
      expect(screen.getByTestId('access-portal-btn')).toBeInTheDocument();
    });
  });
});
