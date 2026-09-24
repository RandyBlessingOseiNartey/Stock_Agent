import { useMemo } from 'react'

import type { StackedBarPlusLineChart } from '../../lib/types'
import { EmptyChart, Panel } from './Panel'
import { axis, baseLayout, SERIES, seriesEntries } from './theme'

/**
 * Balance sheet. Top: two stacks per year side by side — what the company
 * owns (assets) next to how it's funded (liabilities + equity). Bottom:
 * the working-capital and total-debt trend.
 */
export default function StackedBarPlusLine({ chart }: { chart: StackedBarPlusLineChart }) {
  const { bars, lines } = useMemo(() => {
    const groups: [string, string, [string, (number | null)[]][]][] = [
      ['assets', 'Assets', seriesEntries(chart.stacked_bar_series)],
      ['claims', 'Liabilities & Equity', seriesEntries(chart.stacked_bar_series_liabilities)],
    ]
    let slot = 0
    const bars = groups.flatMap(([group, groupTitle, entries]) =>
      entries.map(([name, values], i) => ({
        type: 'bar',
        name,
        x: chart.x_axis,
        y: values,
        offsetgroup: group,
        legendgroup: group,
        legendgrouptitle: i === 0 ? { text: groupTitle, font: { size: 11 } } : undefined,
        marker: { color: SERIES[slot++ % SERIES.length], line: { color: '#242424', width: 2 } },
        hovertemplate: `${name}: %{y:,.2f}B<extra>${groupTitle}</extra>`,
      })),
    )
    const lines = seriesEntries(chart.line_series).map(([name, values], i) => ({
      type: 'scatter',
      mode: 'lines+markers',
      name,
      x: chart.x_axis,
      y: values,
      line: { width: 2, color: SERIES[i % SERIES.length] },
      marker: { size: 8 },
      hovertemplate: `${name}: %{y:,.2f}B<extra></extra>`,
    }))
    return { bars, lines }
  }, [chart])

  if (chart.x_axis.length === 0) return <EmptyChart message="No balance sheet data available." />

  const unit = chart.stacked_bar_series.unit ?? 'USD Billions'
  return (
    <>
      <Panel
        caption={`Composition · ${unit}`}
        data={bars}
        height={320}
        layout={baseLayout({
          barmode: 'relative',
          hovermode: 'closest',
          xaxis: axis({ type: 'category' }),
          legend: { ...(baseLayout().legend as object), groupclick: 'toggleitem' },
        })}
      />
      <Panel
        caption={`Working capital & debt · ${chart.line_series.unit ?? unit}`}
        data={lines}
        height={220}
        layout={baseLayout({ hovermode: 'x unified', xaxis: axis({ type: 'category' }) })}
      />
    </>
  )
}
