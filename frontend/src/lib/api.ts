export type AppView = 'research' | 'council' | 'archive' | 'lab' | 'audit' | 'docs';

export const API_BASE =
  import.meta.env.VITE_API_REST_URL || 'http://127.0.0.1:8090';

export const WS_BASE =
  import.meta.env.VITE_API_WSS_URL || 'ws://127.0.0.1:8090';

export function paperBasename(path: string): string {
  if (!path) return '';
  const parts = path.replace(/\\/g, '/').split('/');
  return parts[parts.length - 1] || path;
}

export async function apiGet(path: string): Promise<Response> {
  return fetch(`${API_BASE}${path}`);
}

export async function apiPost(path: string, body?: unknown): Promise<Response> {
  return fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}
