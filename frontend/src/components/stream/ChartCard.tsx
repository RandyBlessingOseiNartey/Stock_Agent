import { Component, lazy, memo, Suspense, type ReactNode } from 'react'

import { toolLabel } from '../../lib/labels'
import type { ChartItem } from '../../lib/types'
import { BrandLoader } from '../brand/BrandLoader'

// Plotly is by far the heaviest dependency; it's only fetched the first
// time a chart actually needs to render.
const ChartRenderer = lazy(() => import('../charts/ChartRenderer'))

/**
 * Wraps the lazy import itself, so a failed chunk load *or* a malformed
 * payload only ever costs that one chart — never the report or chat
 * message it sits in, and never the rest of the app.
 */
class ChartBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() {
    return { failed: true }
  }
  componentDidCatch(error: unknown) {
    console.error('[chart] render failed', error)
  }
  render() {
    return this.state.failed ? (
      <p className="chart-unavailable">Chart unavailable — the data couldn't be drawn.</p>
    ) : (
      this.props.children
    )
  }
}

/**
 * One chart slot. A per-chart failure renders as a small inline note —
 * one missing chart never blocks or fails the rest of the response.
 * Memoized: parents re-render on every streamed token batch, and a chart
 * whose item hasn't changed must not re-run Plotly.
 */
export const ChartCard = memo(function ChartCard({ item }: { item: ChartItem }) {
  if (!item.chart) {
    return (
      <p className="chart-unavailable">
        Chart unavailable{item.tool ? ` (${toolLabel(item.tool)})` : ''}
        {item.error ? ` — ${item.error}` : ''}
      </p>
    )
  }
  return (
    <figure className="chart-card">
      <figcaption className="chart-card__title">{item.chart.title}</figcaption>
      <ChartBoundary>
        <Suspense
          fallback={
            <div className="chart-card__placeholder">
              <BrandLoader />
            </div>
          }
        >
          <ChartRenderer chart={item.chart} />
        </Suspense>
      </ChartBoundary>
    </figure>
  )
})

export function ChartGrid({ items }: { items: ChartItem[] }) {
  if (items.length === 0) return null
  return (
    <section className="chart-grid" aria-label="Charts">
      {items.map((item) => (
        <ChartCard key={item.id} item={item} />
      ))}
    </section>
  )
}
