export const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

/** localStorage keys holding per-session result data (may contain patient
 *  details in error messages) — cleared on any logout or session expiry. */
export const SESSION_STORAGE_KEYS = ['validation_results'];

export function clearSessionData(): void {
  SESSION_STORAGE_KEYS.forEach(k => localStorage.removeItem(k));
}

/**
 * Thin fetch wrapper that always sends the session cookie and sets
 * Content-Type to JSON unless the body is FormData (file uploads).
 *
 * Any 401 outside the auth endpoints means the session expired server-side:
 * local result data is cleared and the user is sent back to the login page.
 */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const res = await fetch(`${API}${path}`, { ...init, credentials: 'include', headers });

  if (res.status === 401 && !path.startsWith('/api/auth/')) {
    clearSessionData();
    if (window.location.pathname !== '/login') {
      window.location.assign('/login');
    }
  }

  return res;
}

/** Extract the filename from a Content-Disposition header, if present. */
function filenameFromDisposition(disposition: string | null): string | null {
  if (!disposition) return null;
  const match = /filename\*?=(?:UTF-8''|")?([^";]+)"?/i.exec(disposition);
  return match ? decodeURIComponent(match[1].trim()) : null;
}

/**
 * Fetch a protected file download and save it with its server-provided
 * filename (falling back to the last path segment).
 */
export async function downloadFile(path: string, fallbackName?: string): Promise<void> {
  const res = await apiFetch(path);
  if (!res.ok) throw new Error(`Download failed (${res.status})`);

  const filename =
    filenameFromDisposition(res.headers.get('Content-Disposition')) ||
    fallbackName ||
    path.split('/').filter(Boolean).pop() ||
    'download';

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
