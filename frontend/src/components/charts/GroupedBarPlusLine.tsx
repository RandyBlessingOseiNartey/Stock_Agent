import { useMemo } from 'react'

import type { GroupedBarPlusLineChart } from '../../lib/types'
import { EmptyChart, Panel } from './Panel'
import { axis, baseLayout, SERIES, seriesEntries } from './theme'

// Each margin line wears the color of the profit tier it's derived from,
// so "Gross Margin" visibly belongs to "Gross Profit", and so on.
const MARGIN_TO_BAR: Record<string, string> = {
  'Gross Margin': 'Gross Profit',
  'Operating Margin': 'Operating Income',
  'Net Margin': 'Net Income',
}

/**
 * Income statement. The spec's "bars + margin line overlay" mixes USD and
 * percent — rendered as two stacked panels sharing the year axis rather
 * than one dual-axis chart, which would make the two scales look comparable.
 */
export default function GroupedBarPlusLine({ chart }: { chart: GroupedBarPlusLineChart }) {
  const { bars, lines } = useMemo(() => {
    const barEntries = seriesEntries(chart.bar_series)
    const colorOf = new Map(barEntries.map(([name], i) => [name, SERIES[i % SERIES.length]]))
    const bars = barEntries.map(([name, values]) => ({
      type: 'bar',
      name,
      x: chart.x_axis,
      y: values,
      marker: { color: colorOf.get(name), cornerradius: 4 },
      hovertemplate: `${name}: %{y:,.2f}B<extra></extra>`,
    }))
    const lines = seriesEntries(chart.line_series).map(([name, values], i) => ({
      type: 'scatter',
      mode: 'lines+markers',
      name,
      x: chart.x_axis,
      y: values,
      line: { width: 2, color: colorOf.get(MARGIN_TO_BAR[name]) ?? SERIES[i % SERIES.length] },
      marker: { size: 8 },
      connectgaps: false,
      hovertemplate: `${name}: %{y:.1f}%<extra></extra>`,
    }))
    return { bars, lines }
  }, [chart])

  if (chart.x_axis.length === 0) return <EmptyChart message="No income statement data available." />

  return (
    <>
      <Panel
        caption={`${chart.bar_series.unit ?? 'USD Billions'}`}
        data={bars}
        height={290}
        layout={baseLayout({ barmode: 'group', hovermode: 'x unified', xaxis: axis({ type: 'category' }) })}
      />
      <Panel
        caption="Margins (%)"
        data={lines}
        height={220}
        layout={baseLayout({
          hovermode: 'x unified',
          xaxis: axis({ type: 'category' }),
          yaxis: axis({ ticksuffix: '%', zeroline: true }),
        })}
      />
    </>
  )
}
