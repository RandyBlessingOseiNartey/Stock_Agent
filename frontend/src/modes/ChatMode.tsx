import { memo, useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'

import { LoaderStage } from '../components/brand/LoaderStage'
import { WorkingMark } from '../components/brand/WorkingMark'
import { Wordmark } from '../components/brand/Wordmark'
import { ChatComposer } from '../components/composer/ChatComposer'
import { ChartCard } from '../components/stream/ChartCard'
import { ErrorState } from '../components/stream/ErrorState'
import { Report } from '../components/stream/Report'
import { ToolTrace } from '../components/stream/ToolTrace'
import { getJSON } from '../lib/api'
import { toolLabel, uid } from '../lib/labels'
import { isAbort, streamChat } from '../lib/sse'
import { BOOKKEEPING_EVENTS, toChartItem, traceEnd, traceStart } from '../lib/streamState'
import type {
  ChartItem,
  ChatEvent,
  ConversationSummary,
  ResponseStyle,
  StoredMessage,
  TraceItem,
} from '../lib/types'
import { useStreamController } from '../lib/useStreamController'

// ── Message model ──────────────────────────────────────────────────

/** An assistant reply is an ordered list of parts: charts land inline, where they arrived. */
type Part = { kind: 'text'; id: string; text: string } | { kind: 'chart'; id: string; item: ChartItem }

interface UserMessage {
  id: string
  role: 'user'
  text: string
}

interface AssistantMessage {
  id: string
  role: 'assistant'
  status: 'streaming' | 'done' | 'failed'
  pending: boolean
  parts: Part[]
  trace: TraceItem[]
  retry: { attempt: number; max_retries: number } | null
  error: string | null
}

type Message = UserMessage | AssistantMessage

function applyToAssistant(m: AssistantMessage, e: ChatEvent): AssistantMessage {
  const next = BOOKKEEPING_EVENTS.has(e.type) ? m : { ...m, pending: false }
  switch (e.type) {
    case 'tool_start':
      return { ...next, trace: traceStart(next.trace, e.tool) }
    case 'tool_end':
      return { ...next, trace: traceEnd(next.trace, e.tool) }
    case 'retry':
      // The whole turn re-runs: its trace (and any charts) replay from the top.
      return { ...next, retry: { attempt: e.attempt, max_retries: e.max_retries }, trace: [], parts: [] }
    case 'chart':
      return { ...next, parts: [...next.parts, { kind: 'chart', id: uid('part'), item: toChartItem(e) }] }
    case 'token': {
      const last = next.parts[next.parts.length - 1]
      if (last?.kind === 'text') {
        return { ...next, retry: null, parts: [...next.parts.slice(0, -1), { ...last, text: last.text + e.content }] }
      }
      return { ...next, retry: null, parts: [...next.parts, { kind: 'text', id: uid('part'), text: e.content }] }
    }
    case 'done':
      return { ...next, status: 'done' }
    case 'failed':
      return { ...next, status: 'failed', error: e.content }
    default:
      return next
  }
}

function fromStored(m: StoredMessage): Message {
  return m.role === 'user'
    ? { id: m.id, role: 'user', text: m.content }
    : {
        id: m.id,
        role: 'assistant',
        status: 'done',
        pending: false,
        parts: [{ kind: 'text', id: `${m.id}-text`, text: m.content }],
        trace: [],
        retry: null,
        error: null,
      }
}

const isTerminal = (e: ChatEvent) => e.type === 'done' || e.type === 'failed'

const SUGGESTIONS = [
  'Compare Apple and Microsoft on margins and free cash flow',
  "Evaluate Nvidia using Peter Lynch's philosophy",
  'Build a conservative dividend portfolio of 5 US stocks',
  'Show me Tesla’s price history and explain the trend',
]

type History = { status: 'loading' } | { status: 'error'; message: string } | { status: 'ready' }

// ── Mode ───────────────────────────────────────────────────────────

export function ChatMode() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [listState, setListState] = useState<History>({ status: 'loading' })
  const [activeId, setActiveId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [thread, setThread] = useState<History>({ status: 'ready' })
  const [draft, setDraft] = useState('')
  const [responseStyle, setResponseStyle] = useState<ResponseStyle>('balanced')
  const [streaming, setStreaming] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const stream = useStreamController()

  // Tracks the conversation the user is looking at *right now*, so a slow
  // history fetch for a conversation they already left can't overwrite it.
  const viewRef = useRef<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const stickToBottom = useRef(true)

  const refreshList = useCallback(
    () =>
      getJSON<ConversationSummary[]>('/api/chat/conversations')
        .then((items) => {
          setConversations(items)
          setListState({ status: 'ready' })
        })
        .catch((err: Error) => setListState({ status: 'error', message: err.message })),
    [],
  )

  useEffect(() => {
    refreshList()
  }, [refreshList])

  // ── Scrolling: follow the stream unless the user has scrolled up ──
  const onScroll = () => {
    const el = scrollRef.current
    if (!el) return
    stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80
  }
  useLayoutEffect(() => {
    const el = scrollRef.current
    if (el && stickToBottom.current) el.scrollTop = el.scrollHeight
  }, [messages])

  // ── Conversation switching ──
  const startNewChat = () => {
    stream.abort()
    setStreaming(false)
    viewRef.current = null
    setActiveId(null)
    setMessages([])
    setThread({ status: 'ready' })
    setSidebarOpen(false)
  }

  const openConversation = async (id: string) => {
    if (id === activeId && !streaming) return
    stream.abort()
    setStreaming(false)
    viewRef.current = id
    setActiveId(id)
    setMessages([])
    setSidebarOpen(false)
    setThread({ status: 'loading' })
    try {
      const stored = await getJSON<StoredMessage[]>(`/api/chat/conversations/${id}/messages`)
      if (viewRef.current !== id) return
      stickToBottom.current = true
      setMessages(stored.map(fromStored))
      setThread({ status: 'ready' })
    } catch (err) {
      if (viewRef.current !== id || isAbort(err)) return
      setThread({ status: 'error', message: (err as Error).message })
    }
  }

  // ── Sending ──
  const send = (text: string) => {
    const message = text.trim()
    if (!message || streaming) return
    const assistantId = uid('assistant')
    const conversationAtSend = activeId

    stickToBottom.current = true
    setDraft('')
    setStreaming(true)
    setMessages((prev) => [
      ...prev,
      { id: uid('user'), role: 'user', text: message },
      { id: assistantId, role: 'assistant', status: 'streaming', pending: true, parts: [], trace: [], retry: null, error: null },
    ])

    const updateAssistant = (fn: (m: AssistantMessage) => AssistantMessage) =>
      setMessages((prev) => prev.map((m) => (m.id === assistantId && m.role === 'assistant' ? fn(m) : m)))

    void stream.start<ChatEvent>({
      open: (opts) =>
        streamChat({ conversation_id: conversationAtSend, message, response_style: responseStyle }, opts),
      isTerminal,
      onEvents: (events) => {
        for (const e of events) {
          if (e.type === 'conversation_created') {
            viewRef.current = e.conversation_id
            setActiveId(e.conversation_id)
            setConversations((prev) => [
              { id: e.conversation_id, title: null, updated_at: new Date().toISOString() },
              ...prev.filter((c) => c.id !== e.conversation_id),
            ])
          } else if (e.type === 'title_generated') {
            setConversations((prev) => prev.map((c) => (c.id === e.conversation_id ? { ...c, title: e.title } : c)))
          }
        }
        updateAssistant((m) => events.reduce(applyToAssistant, m))
      },
      onError: (errorMessage) =>
        updateAssistant((m) => ({ ...m, status: 'failed', pending: false, error: errorMessage })),
      onSettled: () => {
        setStreaming(false)
        void refreshList() // picks up the new ordering (updated_at) server-side
      },
    })
  }

  const retryLast = () => {
    const lastUser = [...messages].reverse().find((m): m is UserMessage => m.role === 'user')
    if (!lastUser) return
    // Drop the failed exchange; it'll be re-sent (and re-saved) as a new turn.
    setMessages((prev) => prev.slice(0, prev.lastIndexOf(lastUser)))
    send(lastUser.text)
  }

  const activeTitle = conversations.find((c) => c.id === activeId)?.title
  const empty = messages.length === 0 && thread.status === 'ready'

  return (
    <div className={`mode mode--chat ${sidebarOpen ? 'sidebar-open' : ''}`}>
      <aside className="chat-sidebar" aria-label="Conversations">
        <button type="button" className="btn-new-chat" onClick={startNewChat}>
          <span aria-hidden="true">+</span> New Chat
        </button>
        <p className="chat-sidebar__heading">Recent</p>
        <LoaderStage pending={listState.status === 'loading'} reserve={52}>
          {listState.status === 'error' && (
            <p className="chat-sidebar__note">Chat history is unavailable right now. {listState.message}</p>
          )}
          {listState.status === 'ready' && conversations.length === 0 && (
            <p className="chat-sidebar__note">No conversations yet.</p>
          )}
          <ul className="conversation-list">
            {conversations.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  className={`conversation-item ${c.id === activeId ? 'is-active' : ''}`}
                  aria-current={c.id === activeId ? 'true' : undefined}
                  onClick={() => void openConversation(c.id)}
                >
                  {c.title || 'New conversation'}
                </button>
              </li>
            ))}
          </ul>
        </LoaderStage>
      </aside>
      <button
        type="button"
        className="chat-sidebar__scrim"
        aria-label="Close conversation list"
        tabIndex={sidebarOpen ? 0 : -1}
        onClick={() => setSidebarOpen(false)}
      />

      <section className="chat-main">
        <div className="chat-topbar">
          <button
            type="button"
            className="btn-icon chat-topbar__menu"
            aria-label="Show conversations"
            aria-expanded={sidebarOpen}
            onClick={() => setSidebarOpen((o) => !o)}
          >
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <path d="M2.5 4h11M2.5 8h11M2.5 12h11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
          <span className="chat-topbar__title">{activeId ? activeTitle || 'New conversation' : 'New chat'}</span>
        </div>

        <div className="chat-scroll" ref={scrollRef} onScroll={onScroll}>
          <div className="chat-thread">
            {empty && <EmptyState onPick={send} />}
            {thread.status === 'loading' && <LoaderStage pending reserve={160} />}
            {thread.status === 'error' && (
              <ErrorState
                title="Couldn't open this conversation"
                message={thread.message}
                onRetry={() => activeId && void openConversation(activeId)}
              />
            )}
            {messages.map((m) =>
              m.role === 'user' ? (
                <div key={m.id} className="msg msg--user">
                  <p>{m.text}</p>
                </div>
              ) : (
                <AssistantBubble key={m.id} message={m} onRetry={m.status === 'failed' ? retryLast : undefined} />
              ),
            )}
          </div>
        </div>

        <div className="chat-composer">
          <ChatComposer
            value={draft}
            onChange={setDraft}
            responseStyle={responseStyle}
            onResponseStyleChange={setResponseStyle}
            onSubmit={() => send(draft)}
            busy={streaming}
          />
          <p className="chat-composer__hint">StockAgent only states figures it retrieved from a data tool. Not investment advice.</p>
        </div>
      </section>
    </div>
  )
}

// ── Pieces ─────────────────────────────────────────────────────────

const AssistantBubble = memo(function AssistantBubble({
  message: m,
  onRetry,
}: {
  message: AssistantMessage
  onRetry?: () => void
}) {
  const live = m.status === 'streaming'
  const hasText = m.parts.some((p) => p.kind === 'text')

  // Once the reply itself is streaming, the words are the signal — the mark
  // keeps animating, but the status line steps out of the way.
  let statusText: string | null = null
  if (live && !hasText) {
    const activeTool = m.trace.find((t) => t.status === 'running')
    statusText = activeTool ? `Calling ${toolLabel(activeTool.tool)}…` : 'Thinking…'
  }

  return (
    <div className="msg msg--assistant">
      {/* The message's own bolt is the indicator: it animates while the
          reply is being produced and settles static when it's done. */}
      <WorkingMark working={live} className="msg__mark" />
      <div className="msg__body">
        <ToolTrace items={m.trace} live={live} retry={m.retry} />
        {statusText && <p className="msg__status">{statusText}</p>}
        {m.parts.map((p) =>
          p.kind === 'text' ? <Report key={p.id} text={p.text} /> : <ChartCard key={p.id} item={p.item} />,
        )}
        {m.status === 'failed' && m.error && <ErrorState title="No response" message={m.error} onRetry={onRetry} />}
      </div>
    </div>
  )
})

function EmptyState({ onPick }: { onPick: (text: string) => void }) {
  return (
    <div className="chat-empty">
      <Wordmark size={34} variant="accent" />
      <p className="chat-empty__lead">Open-ended equity research. Ask anything — comparisons, strategies, portfolios.</p>
      <ul className="chat-empty__suggestions">
        {SUGGESTIONS.map((s) => (
          <li key={s}>
            <button type="button" className="suggestion" onClick={() => onPick(s)}>
              {s}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
