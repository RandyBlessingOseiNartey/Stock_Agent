import { useCallback, useEffect, useState } from 'react'

import { LoaderStage } from '../components/brand/LoaderStage'
import { WorkingMark } from '../components/brand/WorkingMark'
import { TerminalComposer } from '../components/composer/TerminalComposer'
import { ChartGrid } from '../components/stream/ChartCard'
import { ErrorState } from '../components/stream/ErrorState'
import { Report } from '../components/stream/Report'
import { ToolTrace } from '../components/stream/ToolTrace'
import { getJSON } from '../lib/api'
import { analysisLabel, toolLabel } from '../lib/labels'
import { isAbort, streamTerminal } from '../lib/sse'
import { BOOKKEEPING_EVENTS, toChartItem, traceEnd, traceStart } from '../lib/streamState'
import type { AnalysisInfo, ChartItem, ResponseStyle, TerminalEvent, TraceItem } from '../lib/types'
import { useStreamController } from '../lib/useStreamController'

interface Run {
  company: string
  status: 'running' | 'done' | 'failed'
  pending: boolean
  trace: TraceItem[]
  retry: { attempt: number; max_retries: number } | null
  charts: ChartItem[]
  report: string
  error: string | null
}

function applyEvent(run: Run, e: TerminalEvent): Run {
  const next = BOOKKEEPING_EVENTS.has(e.type) ? run : { ...run, pending: false }
  switch (e.type) {
    case 'tool_start':
      return { ...next, trace: traceStart(next.trace, e.tool) }
    case 'tool_end':
      return { ...next, trace: traceEnd(next.trace, e.tool) }
    case 'retry':
      return { ...next, retry: { attempt: e.attempt, max_retries: e.max_retries }, trace: [], charts: [] }
    case 'chart':
      return { ...next, charts: [...next.charts, toChartItem(e)] }
    case 'token':
      return { ...next, report: next.report + e.content, retry: null }
    case 'done':
      return { ...next, status: 'done', report: e.content || next.report }
    case 'failed':
      return { ...next, status: 'failed', error: e.content }
    default:
      return next
  }
}

const isTerminal = (e: TerminalEvent) => e.type === 'done' || e.type === 'failed'

type Catalogue = { status: 'loading' } | { status: 'error'; message: string } | { status: 'ready'; items: AnalysisInfo[] }

export function TerminalMode() {
  const [catalogue, setCatalogue] = useState<Catalogue>({ status: 'loading' })
  const [reloadKey, setReloadKey] = useState(0)
  const [selected, setSelected] = useState<AnalysisInfo | null>(null)

  const reload = () => {
    setCatalogue({ status: 'loading' })
    setReloadKey((k) => k + 1)
  }

  useEffect(() => {
    const ctrl = new AbortController()
    getJSON<AnalysisInfo[]>('/api/terminal/analyses', ctrl.signal)
      .then((items) => setCatalogue({ status: 'ready', items }))
      .catch((err) => {
        if (!isAbort(err)) setCatalogue({ status: 'error', message: (err as Error).message })
      })
    return () => ctrl.abort()
  }, [reloadKey])

  return (
    <div className="mode mode--terminal">
      <div className="mode-scroll">
        <div className="page">
          {selected ? (
            <AgentView analysis={selected} onBack={() => setSelected(null)} />
          ) : (
            <>
              <header className="page-head">
                <h1>Terminal</h1>
                <p>Twelve specialist agents, each focused on one dimension of a company. Pick one to begin.</p>
              </header>
              <LoaderStage pending={catalogue.status === 'loading'} reserve={240}>
                {catalogue.status === 'error' && (
                  <ErrorState
                    title="Couldn't load the analysis agents"
                    message={catalogue.message}
                    onRetry={reload}
                  />
                )}
                {catalogue.status === 'ready' && (
                  <ul className="agent-grid">
                    {catalogue.items.map((a) => (
                      <li key={a.key}>
                        <button type="button" className="agent-card" onClick={() => setSelected(a)}>
                          <span className="agent-card__name">{analysisLabel(a.key)}</span>
                          <span className="agent-card__desc">{a.description}</span>
                          <span className="agent-card__meta">{a.tools.length} data tools</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </LoaderStage>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function AgentView({ analysis, onBack }: { analysis: AnalysisInfo; onBack: () => void }) {
  const [company, setCompany] = useState('')
  const [responseStyle, setResponseStyle] = useState<ResponseStyle>('balanced')
  const [run, setRun] = useState<Run | null>(null)
  const stream = useStreamController()
  const label = analysisLabel(analysis.key)

  const submit = useCallback(() => {
    const c = company.trim()
    if (!c) return
    setRun({ company: c, status: 'running', pending: true, trace: [], retry: null, charts: [], report: '', error: null })
    void stream.start<TerminalEvent>({
      open: (opts) =>
        streamTerminal({ analysis_type: analysis.key, company_input: c, response_style: responseStyle }, opts),
      isTerminal,
      onEvents: (events) => setRun((r) => (r ? events.reduce(applyEvent, r) : r)),
      onError: (message) => setRun((r) => (r ? { ...r, status: 'failed', pending: false, error: message } : r)),
    })
  }, [company, responseStyle, analysis.key, stream])

  // Leaving the agent (Back, or the component unmounting) cancels its run.
  const back = () => {
    stream.abort()
    onBack()
  }

  const running = run?.status === 'running'

  // Narrates the run beside the animating mark, start to finish.
  let statusText: string | null = null
  if (running) {
    const activeTool = run.trace.find((t) => t.status === 'running')
    if (run.report) statusText = 'Writing report…'
    else if (activeTool) statusText = `Calling ${toolLabel(activeTool.tool)}…`
    else statusText = run.trace.length ? 'Writing report…' : 'Gathering data…'
  }

  return (
    <>
      <button type="button" className="btn-back" onClick={back}>
        <span aria-hidden="true">←</span> All agents
      </button>
      <header className="page-head">
        <h1>{label}</h1>
        <p>{analysis.description}</p>
        <ul className="tool-chips" aria-label="Data tools this agent uses">
          {analysis.tools.map((t) => (
            <li key={t}>{toolLabel(t)}</li>
          ))}
        </ul>
      </header>

      <TerminalComposer
        value={company}
        onChange={setCompany}
        responseStyle={responseStyle}
        onResponseStyleChange={setResponseStyle}
        onSubmit={submit}
        busy={running}
      />

      {run && (
        <section className="output-pane" aria-live="polite" aria-busy={running}>
          <div className="output-pane__meta">
            <span>
              {label} · <strong>{run.company}</strong>
            </span>
          </div>
          {/* One mark for the whole run: animates until the report is
              finished, then settles into the static bolt in place. */}
          <WorkingMark working={running} status={statusText} className="output-pane__mark" />
          <ToolTrace items={run.trace} live={running} retry={run.retry} />
          <ChartGrid items={run.charts} />
          {run.report && <Report text={run.report} />}
          {run.status === 'failed' && run.error && (
            <ErrorState title="Analysis failed" message={run.error} onRetry={submit} />
          )}
        </section>
      )}
    </>
  )
}
