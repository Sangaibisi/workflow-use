// Single source of truth for the backend base URL.
//
// Previously three different literals ("http://localhost:8000",
// "http://127.0.0.1:8000", and a component-local API_BASE) were scattered
// across the UI, so the app was unusable on any non-default host/port.
//
// Override at build time with VITE_API_BASE_URL; defaults to localhost:8000.
export const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ||
  "http://localhost:8000";

/** Join the API base with a path (leading slash optional). */
export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path.startsWith("/") ? "" : "/"}${path}`;
}
