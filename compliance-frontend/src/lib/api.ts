export const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

/**
 * Thin fetch wrapper that always sends the session cookie and sets
 * Content-Type to JSON unless the body is FormData (file uploads).
 */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  return fetch(`${API}${path}`, { ...init, credentials: 'include', headers });
}

/**
 * Fetch a protected file download and return it as a blob URL.
 * Caller is responsible for calling URL.revokeObjectURL when done.
 */
export async function downloadFile(path: string): Promise<void> {
  const res = await apiFetch(path);
  if (!res.ok) throw new Error(`Download failed (${res.status})`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
