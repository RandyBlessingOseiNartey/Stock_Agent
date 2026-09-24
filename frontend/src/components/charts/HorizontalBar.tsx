import { useMemo } from 'react'

import type { HorizontalBarChart } from '../../lib/types'
import { EmptyChart, Panel } from './Panel'
import { axis, baseLayout, INK, SERIES } from './theme'

/**
 * Peer market caps, ranked. One series, so peers share a neutral mark and
 * only the subject company takes the accent — plus a bold label, so it's
 * never identified by color alone.
 */
export default function HorizontalBar({ chart }: { chart: HorizontalBarChart }) {
  const entries = (chart.entries ?? []).filter((e) => e.symbol)

  const data = useMemo(
    () => [
      {
        type: 'bar',
        orientation: 'h',
        y: entries.map((e) => e.symbol),
        x: entries.map((e) => e.market_cap_b),
        marker: {
          color: entries.map((e) => (e.is_subject ? SERIES[0] : INK.neutralMark)),
          cornerradius: 4,
        },
        text: entries.map((e) => `$${e.market_cap_b.toLocaleString()}B`),
        textposition: 'outside',
        textfont: { color: INK.secondary, size: 11 },
        cliponaxis: false,
        hovertemplate: '%{y}: $%{x:,.2f}B<extra></extra>',
      },
    ],
    [entries],
  )

  if (entries.length === 0) return <EmptyChart message="No peer data available." />

  return (
    <Panel
      caption={`Market cap · ${chart.unit ?? 'USD Billions'}`}
      data={data}
      height={Math.max(160, entries.length * 34 + 40)}
      layout={baseLayout({
        showlegend: false,
        margin: { l: 64, r: 72, t: 8, b: 32 },
        xaxis: axis({ tickprefix: '$', ticksuffix: 'B' }),
        yaxis: axis({
          type: 'category',
          tickvals: entries.map((e) => e.symbol),
          ticktext: entries.map((e) => (e.is_subject ? `<b>${e.symbol}</b>` : e.symbol)),
          tickfont: { color: INK.secondary, size: 12 },
        }),
      })}
    />
  )
}
