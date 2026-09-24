import { EventStreamContentType, fetchEventSource } from '@microsoft/fetch-event-source'

import { baseHeaders, readErrorDetail } from './api'
import type {
  ChatEvent,
  DeepResearchEvent,
  ResponseStyle,
  RiskAppetite,
  TerminalEvent,
} from './types'

/** Thrown for failures the user should see verbatim (already human-readable). */
export class StreamError extends Error {}

interface StreamOptions<E> {
  onEvent: (event: E) => void
  signal: AbortSignal
}

/**
 * POSTs a JSON body and forwards each SSE `data:` payload, parsed, to
 * `onEvent`. Resolves when the server closes the stream; rejects with a
 * StreamError on HTTP errors or a dropped connection. Never retries —
 * re-POSTing would start a second, duplicate agent run on the server.
 */
async function streamPost<E>(path: string, body: unknown, { onEvent, signal }: StreamOptions<E>) {
  await fetchEventSource(path, {
    method: 'POST',
    headers: baseHeaders(),
    body: JSON.stringify(body),
    signal,
    // Without this the library closes the stream when the tab is hidden
    // and silently re-POSTs on return — i.e. a duplicate agent run.
    openWhenHidden: true,
    async onopen(res) {
      const type = res.headers.get('content-type') ?? ''
      if (res.ok && type.startsWith(EventStreamContentType)) return
      throw new StreamError(await readErrorDetail(res))
    },
    onmessage(msg) {
      if (!msg.data) return // keep-alive pings carry no data
      onEvent(JSON.parse(msg.data) as E)
    },
    onerror(err) {
      // Rethrowing stops the library's automatic reconnect: for us every
      // error is terminal for this request.
      if (err instanceof StreamError) throw err
      throw new StreamError('Lost connection to the StockAgent server.')
    },
  })
}

export function streamDeepResearch(
  body: { query: string; response_style: ResponseStyle; risk_appetite: RiskAppetite },
  opts: StreamOptions<DeepResearchEvent>,
) {
  return streamPost('/api/deep-research/stream', body, opts)
}

export function streamTerminal(
  body: { analysis_type: string; company_input: string; response_style: ResponseStyle },
  opts: StreamOptions<TerminalEvent>,
) {
  return streamPost('/api/terminal/stream', body, opts)
}

export function streamChat(
  body: { conversation_id: string | null; message: string; response_style: ResponseStyle },
  opts: StreamOptions<ChatEvent>,
) {
  return streamPost('/api/chat/stream', body, opts)
}

export function isAbort(err: unknown): boolean {
  return (err as Error)?.name === 'AbortError'
}
