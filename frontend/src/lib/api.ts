// TODO: replace with real authentication before any production launch.
// Mirrors backend/deps.py's dev-only stub. It is NOT authentication — anyone
// can send any id, and ids are not secret.
const FALLBACK_USER_ID = '00000000-0000-0000-0000-000000000001'
const STORAGE_KEY = 'stockagent.userId'

/**
 * A per-browser id, generated once and kept in localStorage.
 *
 * On a shared demo link a single hardcoded id would put every visitor in one
 * account: everyone would see (and add to) everyone else's conversations.
 * Giving each browser its own id keeps chat histories separate. Set
 * VITE_USER_ID to pin a specific id instead.
 */
function resolveUserId(): string {
  if (import.meta.env.VITE_USER_ID) return import.meta.env.VITE_USER_ID
  try {
    const existing = localStorage.getItem(STORAGE_KEY)
    if (existing) return existing
    // randomUUID needs a secure context (https or localhost) — fall back if absent.
    const fresh = crypto.randomUUID?.() ?? FALLBACK_USER_ID
    localStorage.setItem(STORAGE_KEY, fresh)
    return fresh
  } catch {
    // Private mode or blocked site data: stay usable, just not separated.
    return FALLBACK_USER_ID
  }
}

export const DEV_USER_ID = resolveUserId()

/** Headers shared by every request, across all three modes. */
export function baseHeaders(): Record<string, string> {
  return { 'Content-Type': 'application/json', 'X-User-Id': DEV_USER_ID }
}

/** Pulls FastAPI's `{"detail": ...}` out of an error response, if present. */
export async function readErrorDetail(res: Response): Promise<string> {
  try {
    const body = await res.json()
    if (typeof body?.detail === 'string') return body.detail
  } catch {
    // Non-JSON error body (e.g. the proxy's own 502 page) — fall through.
  }
  if (res.status === 502 || res.status === 504) {
    return 'The StockAgent server is not reachable. Is the backend running?'
  }
  return `Request failed (${res.status} ${res.statusText})`
}

export async function getJSON<T>(path: string, signal?: AbortSignal): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, { headers: baseHeaders(), signal })
  } catch (err) {
    if ((err as Error).name === 'AbortError') throw err
    throw new Error('The StockAgent server is not reachable. Is the backend running?')
  }
  if (!res.ok) throw new Error(await readErrorDetail(res))
  return res.json() as Promise<T>
}
