import { useCallback, useEffect, useRef } from 'react'

import { isAbort } from './sse'

interface StartOptions<E> {
  /** Opens the SSE request (one of the stream* functions in sse.ts). */
  open: (opts: { onEvent: (event: E) => void; signal: AbortSignal }) => Promise<void>
  /** Events after which the stream counts as having finished properly. */
  isTerminal: (event: E) => boolean
  /** Receives events in batches — at most one call per animation frame. */
  onEvents: (events: E[]) => void
  /** Human-readable failure: HTTP error, dropped connection, early close. */
  onError: (message: string) => void
  /** Runs once the stream ends for any reason other than being aborted. */
  onSettled?: () => void
}

/**
 * Owns one in-flight stream at a time for a mode. Starting a new stream
 * (or unmounting) aborts the previous one.
 *
 * Events are queued and flushed once per animation frame, so a burst of
 * tokens produces one React render instead of dozens — this matters
 * because each render re-parses the growing markdown report.
 */
export function useStreamController() {
  const ctrlRef = useRef<AbortController | null>(null)

  useEffect(() => () => ctrlRef.current?.abort(), [])

  const abort = useCallback(() => {
    ctrlRef.current?.abort()
    ctrlRef.current = null
  }, [])

  const start = useCallback(async <E,>(o: StartOptions<E>) => {
    ctrlRef.current?.abort()
    const ctrl = new AbortController()
    ctrlRef.current = ctrl

    let queue: E[] = []
    let frame = 0
    let sawTerminal = false

    const flush = () => {
      frame = 0
      if (queue.length === 0) return
      const batch = queue
      queue = []
      o.onEvents(batch)
    }
    const flushNow = () => {
      if (frame) cancelAnimationFrame(frame)
      flush()
    }

    try {
      await o.open({
        signal: ctrl.signal,
        onEvent: (event) => {
          if (ctrl.signal.aborted) return
          if (o.isTerminal(event)) sawTerminal = true
          queue.push(event)
          if (!frame) frame = requestAnimationFrame(flush)
        },
      })
      // fetch-event-source resolves (rather than rejects) on abort.
      if (ctrl.signal.aborted) return
      flushNow()
      if (!sawTerminal) o.onError('The connection closed before the response finished.')
    } catch (err) {
      if (ctrl.signal.aborted || isAbort(err)) return
      flushNow()
      o.onError(err instanceof Error ? err.message : String(err))
    } finally {
      if (frame) cancelAnimationFrame(frame)
      if (ctrlRef.current === ctrl) ctrlRef.current = null
      if (!ctrl.signal.aborted) o.onSettled?.()
    }
  }, [])

  return { start, abort }
}
