// TODO: replace with real authentication before any production launch.
// Mirrors backend/deps.py's dev-only stub: every request claims this
// placeholder user. It is NOT authentication — anyone can send any id.
export const DEV_USER_ID = import.meta.env.VITE_USER_ID || '00000000-0000-0000-0000-000000000001'

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
