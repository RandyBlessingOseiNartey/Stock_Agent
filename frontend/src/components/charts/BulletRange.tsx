import { useMemo } from 'react'

import type { BulletRangeChart } from '../../lib/types'
import { EmptyChart, Panel } from './Panel'
import { axis, baseLayout, INK, SERIES } from './theme'

const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)

/**
 * Stock quote: where the current price sits inside its 52-week range, with
 * the moving averages and previous close as labelled reference ticks.
 */
export default function BulletRange({ chart }: { chart: BulletRangeChart }) {
  const { range_low: low, range_high: high, current_value: current } = chart
  const unit = chart.unit ?? 'USD'

  const data = useMemo(() => {
    if (!isNum(low) || !isNum(high)) return null
    const markers = Object.entries(chart.markers ?? {}).filter((m): m is [string, number] => isNum(m[1]))
    const traces: unknown[] = [
      {
        type: 'scatter',
        mode: 'lines',
        x: [low, high],
        y: [0, 0],
        line: { color: 'rgba(255,255,255,0.16)', width: 14 },
        hoverinfo: 'skip',
        showlegend: false,
      },
      {
        type: 'scatter',
        mode: 'markers+text',
        x: [low, high],
        y: [0, 0],
        marker: { symbol: 'line-ns', size: 22, line: { width: 2, color: INK.muted } },
        text: [`52W low<br>${low.toFixed(2)}`, `52W high<br>${high.toFixed(2)}`],
        textposition: 'bottom center',
        textfont: { size: 11, color: INK.muted },
        hovertemplate: '%{text}<extra></extra>',
        showlegend: false,
      },
    ]
    if (markers.length) {
      traces.push({
        type: 'scatter',
        mode: 'markers+text',
        x: markers.map(([, v]) => v),
        y: markers.map(() => 0),
        marker: { symbol: 'line-ns', size: 26, line: { width: 2, color: INK.secondary } },
        // Alternate label side so neighbouring markers don't collide.
        text: markers.map(([name, v]) => `${name}<br>${v.toFixed(2)}`),
        textposition: markers.map((_, i) => (i % 2 ? 'bottom center' : 'top center')),
        textfont: { size: 10, color: INK.secondary },
        hovertemplate: '%{text}<extra></extra>',
        showlegend: false,
      })
    }
    if (isNum(current)) {
      traces.push({
        type: 'scatter',
        mode: 'markers',
        x: [current],
        y: [0],
        marker: { symbol: 'diamond', size: 16, color: SERIES[0], line: { color: '#242424', width: 2 } },
        name: 'Current price',
        hovertemplate: `Current: %{x:.2f} ${unit}<extra></extra>`,
        showlegend: false,
      })
    }
    return traces
  }, [chart, low, high, current, unit])

  if (!data || !isNum(low) || !isNum(high)) return <EmptyChart message="52-week range unavailable." />

  const pad = (high - low) * 0.06 || 1
  const position = isNum(current) && high > low ? ((current - low) / (high - low)) * 100 : null

  return (
    <>
      {isNum(current) && (
        <p className="chart-stat">
          <span className="chart-stat__value">
            {current.toFixed(2)} <small>{unit}</small>
          </span>
          {position !== null && <span className="chart-stat__note">{position.toFixed(0)}% of the way from 52-week low to high</span>}
        </p>
      )}
      <Panel
        data={data}
        height={170}
        layout={baseLayout({
          margin: { l: 24, r: 24, t: 40, b: 48 },
          hovermode: 'closest',
          xaxis: axis({ range: [low - pad, high + pad], showgrid: false, zeroline: false, showticklabels: false }),
          yaxis: axis({ range: [-1, 1], visible: false }),
        })}
      />
    </>
  )
}
