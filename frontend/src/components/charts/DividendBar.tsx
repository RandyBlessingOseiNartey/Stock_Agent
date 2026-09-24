import { useMemo } from 'react'

import type { BarChart } from '../../lib/types'
import { EmptyChart, Panel } from './Panel'
import { axis, baseLayout, SERIES } from './theme'

/**
 * Dividend history (chart_type "bar"). NOTE: get_dividend_history's field
 * names are unverified against a live call — see PROJECT_CONTEXT.md §5.
 */
export default function DividendBar({ chart }: { chart: BarChart }) {
  const data = useMemo(
    () => [
      {
        type: 'bar',
        x: chart.x_axis,
        y: chart.values,
        marker: { color: SERIES[0], cornerradius: 4 },
        hovertemplate: '%{x}: $%{y:.4f} per share<extra></extra>',
      },
    ],
    [chart],
  )

  if (!chart.x_axis?.length) {
    return <EmptyChart message={chart.note ?? 'No dividend history — common for growth companies that pay no dividend.'} />
  }

  return (
    <Panel
      caption="Dividend per share (USD)"
      data={data}
      height={260}
      layout={baseLayout({ showlegend: false, xaxis: axis({ type: 'category', nticks: 12 }), yaxis: axis({ tickprefix: '$' }) })}
    />
  )
}
