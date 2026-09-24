import { useMemo } from 'react'

import type { GaugeSetPlusRadarChart } from '../../lib/types'
import { gaugeTrace } from './gauge'
import { EmptyChart, Panel } from './Panel'
import { baseLayout, INK, SERIES } from './theme'

const ROW_PX = 64

function prettyField(field: string): string {
  return field
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

/** Key metrics: one bullet gauge per benchmarked ratio, plus a margin/return radar. */
export default function GaugeSetPlusRadar({ chart }: { chart: GaugeSetPlusRadarChart }) {
  const gauges = useMemo(() => chart.gauges ?? [], [chart])
  const radarEntries = useMemo(() => Object.entries(chart.radar?.values ?? {}), [chart])

  const gaugeData = useMemo(() => {
    const n = gauges.length
    return gauges.map((g, i) => {
      // Rows from top to bottom, with a little breathing room between them.
      const top = 1 - i / n
      const bottom = 1 - (i + 1) / n
      const pad = (top - bottom) * 0.22
      return gaugeTrace(g, { x: [0.3, 0.9], y: [bottom + pad, top - pad] })
    })
  }, [gauges])

  const radarData = useMemo(() => {
    if (radarEntries.length < 3) return null
    const labels = radarEntries.map(([k]) => prettyField(k))
    const values = radarEntries.map(([, v]) => v)
    return [
      {
        type: 'scatterpolar',
        r: [...values, values[0]],
        theta: [...labels, labels[0]],
        fill: 'toself',
        fillcolor: 'rgba(47,107,255,0.22)',
        line: { color: SERIES[0], width: 2 },
        marker: { size: 8, color: SERIES[0] },
        name: 'Latest period',
        hovertemplate: '%{theta}: %{r:.1f}%<extra></extra>',
      },
    ]
  }, [radarEntries])

  if (gauges.length === 0 && !radarData) return <EmptyChart message="No key metrics available to chart." />

  const minR = Math.min(0, ...radarEntries.map(([, v]) => v))

  return (
    <div className="chart-split">
      {gauges.length > 0 && (
        <Panel
          caption="Against benchmark bands"
          data={gaugeData}
          height={Math.max(ROW_PX * gauges.length, 120)}
          layout={baseLayout({ margin: { l: 8, r: 8, t: 8, b: 8 } })}
        />
      )}
      {radarData && (
        <Panel
          caption={`Margins & returns (${chart.radar.unit === 'Percent' ? '%' : chart.radar.unit ?? '%'})`}
          data={radarData}
          height={320}
          layout={baseLayout({
            margin: { l: 56, r: 56, t: 24, b: 24 },
            showlegend: false,
            polar: {
              bgcolor: 'rgba(0,0,0,0)',
              radialaxis: {
                range: [minR, Math.max(...radarEntries.map(([, v]) => v), 1) * 1.1],
                ticksuffix: '%',
                gridcolor: INK.grid,
                linecolor: INK.axis,
                tickfont: { size: 10, color: INK.muted },
              },
              angularaxis: { gridcolor: INK.grid, linecolor: INK.axis, tickfont: { size: 11, color: INK.secondary } },
            },
          })}
        />
      )}
    </div>
  )
}
