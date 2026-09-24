import { useCallback, useState } from 'react'

import { WorkingMark } from '../components/brand/WorkingMark'
import { DeepResearchComposer } from '../components/composer/DeepResearchComposer'
import { ChartGrid } from '../components/stream/ChartCard'
import { ErrorState } from '../components/stream/ErrorState'
import { Report } from '../components/stream/Report'
import { ToolTrace } from '../components/stream/ToolTrace'
import { RISK_APPETITE_OPTIONS, toolLabel } from '../lib/labels'
import { streamDeepResearch } from '../lib/sse'
import { BOOKKEEPING_EVENTS, toChartItem, traceEnd, traceStart } from '../lib/streamState'
import type { ChartItem, DeepResearchEvent, ResponseStyle, RiskAppetite, TraceItem } from '../lib/types'
import { useStreamController } from '../lib/useStreamController'

interface Run {
  query: string
  riskAppetite: RiskAppetite
  status: 'running' | 'done' | 'failed'
  /** Dispatched, but nothing meaningful has arrived yet → BrandLoader. */
  pending: boolean
  stage: 'retriever' | 'investment_brief' | null
  trace: TraceItem[]
  retry: { attempt: number; max_retries: number } | null
  charts: ChartItem[]
  report: string
  error: string | null
}

function applyEvent(run: Run, e: DeepResearchEvent): Run {
  const next = BOOKKEEPING_EVENTS.has(e.type) ? run : { ...run, pending: false }
  switch (e.type) {
    case 'stage':
      return e.status === 'start' ? { ...next, stage: e.stage ?? null } : next
    case 'tool_start':
      return { ...next, trace: traceStart(next.trace, e.tool) }
    case 'tool_end':
      return { ...next, trace: traceEnd(next.trace, e.tool) }
    case 'retry':
      // The retriever re-runs from scratch and re-emits its whole trace.
      return { ...next, retry: { attempt: e.attempt, max_retries: e.max_retries }, trace: [], charts: [] }
    case 'chart':
      return { ...next, charts: [...next.charts, toChartItem(e)] }
    case 'retriever_done':
      return { ...next, retry: null } // internal JSON — never rendered
    case 'token':
      return { ...next, report: next.report + e.content }
    case 'brief_done':
      return { ...next, status: 'done', report: e.content || next.report }
    case 'retriever_failed':
    case 'failed':
      return { ...next, status: 'failed', error: e.content }
    default:
      return next
  }
}

const isTerminal = (e: DeepResearchEvent) => ['brief_done', 'retriever_failed', 'failed'].includes(e.type)

export function DeepResearchMode() {
  const [query, setQuery] = useState('')
  const [riskAppetite, setRiskAppetite] = useState<RiskAppetite>('moderate')
  const [responseStyle, setResponseStyle] = useState<ResponseStyle>('balanced')
  const [run, setRun] = useState<Run | null>(null)
  const stream = useStreamController()

  const submit = useCallback(() => {
    const q = query.trim()
    if (!q) return
    setRun({
      query: q,
      riskAppetite,
      status: 'running',
      pending: true,
      stage: null,
      trace: [],
      retry: null,
      charts: [],
      report: '',
      error: null,
    })
    void stream.start<DeepResearchEvent>({
      open: (opts) => streamDeepResearch({ query: q, response_style: responseStyle, risk_appetite: riskAppetite }, opts),
      isTerminal,
      onEvents: (events) => setRun((r) => (r ? events.reduce(applyEvent, r) : r)),
      onError: (message) => setRun((r) => (r ? { ...r, status: 'failed', pending: false, error: message } : r)),
    })
  }, [query, riskAppetite, responseStyle, stream])

  const running = run?.status === 'running'
  const riskLabel = RISK_APPETITE_OPTIONS.find((o) => o.value === run?.riskAppetite)?.label

  // Narrates the run beside the animating mark, start to finish.
  let statusText: string | null = null
  if (running) {
    const activeTool = run.trace.find((t) => t.status === 'running')
    if (run.stage === 'investment_brief') statusText = 'Writing investment brief…'
    else if (activeTool) statusText = `Calling ${toolLabel(activeTool.tool)}…`
    else if (run.pending) statusText = 'Retrieving sources…'
    else statusText = run.trace.length ? 'Analyzing retrieved data…' : 'Retrieving sources…'
  }

  return (
    <div className="mode mode--deep-research">
      <div className="mode-scroll">
        <div className="page">
          <header className="page-head">
            <h1>Deep Research</h1>
            <p>One query in, one full 13-section investment brief out — every figure pulled from a live data tool.</p>
          </header>

          <DeepResearchComposer
            value={query}
            onChange={setQuery}
            riskAppetite={riskAppetite}
            onRiskAppetiteChange={setRiskAppetite}
            responseStyle={responseStyle}
            onResponseStyleChange={setResponseStyle}
            onSubmit={submit}
            busy={running}
          />

          {run && (
            <section className="output-pane" aria-live="polite" aria-busy={running}>
              <div className="output-pane__meta">
                <span>
                  Investment brief · <strong>{run.query}</strong>
                </span>
                {riskLabel && <span className="pill">{riskLabel} risk</span>}
              </div>

              {/* One mark for the whole run: animates until the brief is
                  finished, then settles into the static bolt in place. */}
              <WorkingMark working={running} status={statusText} className="output-pane__mark" />
              <ToolTrace items={run.trace} live={running} retry={run.retry} />
              <ChartGrid items={run.charts} />
              {run.report && <Report text={run.report} />}
              {run.status === 'failed' && run.error && (
                <ErrorState title="Research failed" message={run.error} onRetry={submit} />
              )}
            </section>
          )}
        </div>
      </div>
    </div>
  )
}
