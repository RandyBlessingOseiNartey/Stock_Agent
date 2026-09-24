import { useState, type KeyboardEvent } from 'react'

import { Wordmark } from './components/brand/Wordmark'
import { ChatMode } from './modes/ChatMode'
import { DeepResearchMode } from './modes/DeepResearchMode'
import { TerminalMode } from './modes/TerminalMode'

type Mode = 'chat' | 'terminal' | 'deep-research'

const MODES: { id: Mode; label: string }[] = [
  { id: 'chat', label: 'Chat' },
  { id: 'terminal', label: 'Terminal' },
  { id: 'deep-research', label: 'Deep Research' },
]

export default function App() {
  // Chat is the main interface and the default view on load.
  const [mode, setMode] = useState<Mode>('chat')

  // Arrow keys move between tabs (WAI-ARIA tabs pattern).
  const onTabKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return
    const i = MODES.findIndex((m) => m.id === mode)
    const next = MODES[(i + (e.key === 'ArrowRight' ? 1 : MODES.length - 1)) % MODES.length]
    setMode(next.id)
    document.getElementById(`tab-${next.id}`)?.focus()
  }

  return (
    <div className="app">
      <header className="app-header">
        <Wordmark size={20} className="app-header__brand" />
        <div className="mode-tabs" role="tablist" aria-label="Modes" onKeyDown={onTabKey}>
          {MODES.map((m) => (
            <button
              key={m.id}
              id={`tab-${m.id}`}
              type="button"
              role="tab"
              className="mode-tab"
              aria-selected={mode === m.id}
              aria-controls={`panel-${m.id}`}
              tabIndex={mode === m.id ? 0 : -1}
              onClick={() => setMode(m.id)}
            >
              {m.label}
            </button>
          ))}
        </div>
      </header>

      {/*
        All three modes stay mounted and are only hidden, so switching tabs
        never kills an in-flight stream or loses a finished report. They
        share nothing but the auth header.
      */}
      {MODES.map((m) => (
        <main
          key={m.id}
          id={`panel-${m.id}`}
          role="tabpanel"
          aria-labelledby={`tab-${m.id}`}
          className="app-panel"
          hidden={mode !== m.id}
        >
          {m.id === 'chat' && <ChatMode />}
          {m.id === 'terminal' && <TerminalMode />}
          {m.id === 'deep-research' && <DeepResearchMode />}
        </main>
      ))}
    </div>
  )
}
