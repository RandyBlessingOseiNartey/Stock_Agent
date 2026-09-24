import { useMemo } from 'react'

import type { DonutPlusGaugeChart } from '../../lib/types'
import { gaugeTrace } from './gauge'
import { Panel } from './Panel'
import { baseLayout, SERIES } from './theme'

/** Share statistics: ownership split as a donut + short interest as a benchmarked gauge. */
export default function DonutPlusGauge({ chart }: { chart: DonutPlusGaugeChart }) {
  const donut = useMemo(() => {
    const entries = Object.entries(chart.donut ?? {})
    return [
      {
        type: 'pie',
        hole: 0.62,
        sort: false,
        labels: entries.map(([k]) => k),
        values: entries.map(([, v]) => v),
        marker: { colors: SERIES.slice(0, entries.length), line: { color: '#242424', width: 2 } },
        // Values are already percentages of shares outstanding.
        texttemplate: '%{label}<br>%{value:.1f}%',
        textposition: 'outside',
        hovertemplate: '%{label}: %{value:.2f}%<extra></extra>',
      },
    ]
  }, [chart])

  const gauge = useMemo(
    () => [gaugeTrace({ ...chart.gauge, unit: '%' }, { x: [0.3, 0.9], y: [0.15, 0.85] })],
    [chart],
  )

  const daysToCover = chart.gauge?.days_to_cover

  return (
    <div className="chart-split">
      <Panel
        caption="Ownership (% of shares)"
        data={donut}
        height={280}
        layout={baseLayout({ showlegend: false, margin: { l: 40, r: 40, t: 24, b: 24 } })}
      />
      <div>
        <Panel caption="Short interest" data={gauge} height={96} layout={baseLayout({ margin: { l: 8, r: 8, t: 8, b: 8 } })} />
        {typeof daysToCover === 'number' && (
          <p className="chart-stat__note">Days to cover: {daysToCover.toFixed(2)}</p>
        )}
      </div>
    </div>
  )
}
