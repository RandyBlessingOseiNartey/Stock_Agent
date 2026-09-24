import { uid } from './labels'
import type { ChartItem, ChartSpec, TraceItem } from './types'

/** Pure trace transitions shared by all three modes. */
export function traceStart(trace: TraceItem[], tool: string): TraceItem[] {
  return [...trace, { id: uid('tool'), tool, status: 'running' }]
}

export function traceEnd(trace: TraceItem[], tool: string): TraceItem[] {
  // Tools can run in parallel (and the same tool twice) — close the
  // oldest still-running call of that name.
  const index = trace.findIndex((t) => t.tool === tool && t.status === 'running')
  if (index === -1) return trace
  const next = trace.slice()
  next[index] = { ...next[index], status: 'done' }
  return next
}

export function toChartItem(event: { tool?: string; chart?: ChartSpec; error?: string }): ChartItem {
  return { id: uid('chart'), tool: event.tool, chart: event.chart, error: event.error }
}

/** Events that are pure bookkeeping — they don't end the loading state. */
export const BOOKKEEPING_EVENTS = new Set(['stage', 'conversation_created'])
