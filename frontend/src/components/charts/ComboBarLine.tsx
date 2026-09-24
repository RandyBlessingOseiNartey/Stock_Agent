import { useMemo } from 'react'

import type { ComboBarLineChart } from '../../lib/types'
import { EmptyChart, Panel } from './Panel'
import { axis, baseLayout, SERIES, seriesEntries } from './theme'

/** Cash flow: OCF / CapEx / SBC as bars, Free Cash Flow as a line — one USD axis. */
export default function ComboBarLine({ chart }: { chart: ComboBarLineChart }) {
  const data = useMemo(() => {
    const barEntries = seriesEntries(chart.bar_series)
    const bars = barEntries.map(([name, values], i) => ({
      type: 'bar',
      name,
      x: chart.x_axis,
      y: values,
      marker: { color: SERIES[i % SERIES.length], cornerradius: 4 },
      hovertemplate: `${name}: %{y:,.2f}B<extra></extra>`,
    }))
    const lines = seriesEntries(chart.line_series).map(([name, values], i) => ({
      type: 'scatter',
      mode: 'lines+markers',
      name,
      x: chart.x_axis,
      y: values,
      line: { width: 2, color: SERIES[(barEntries.length + i) % SERIES.length] },
      marker: { size: 8, line: { color: '#242424', width: 2 } },
      hovertemplate: `${name}: %{y:,.2f}B<extra></extra>`,
    }))
    return [...bars, ...lines]
  }, [chart])

  if (chart.x_axis.length === 0) return <EmptyChart message="No cash flow data available." />

  return (
    <Panel
      caption={chart.bar_series.unit ?? 'USD Billions'}
      data={data}
      height={320}
      layout={baseLayout({ barmode: 'group', hovermode: 'x unified', xaxis: axis({ type: 'category' }) })}
    />
  )
}
