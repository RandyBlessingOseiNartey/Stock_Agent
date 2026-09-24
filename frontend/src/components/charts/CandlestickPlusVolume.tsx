import { useMemo } from 'react'

import type { CandlestickPlusVolumeChart } from '../../lib/types'
import { EmptyChart, Panel } from './Panel'
import { axis, baseLayout, INK, SERIES } from './theme'

// Up/down is polarity: blue ↔ orange is a colorblind-safe pair (unlike the
// conventional green ↔ red), and candle body shape carries direction too.
const UP = SERIES[0]
const DOWN = SERIES[1]

/**
 * Price history. The x-axis is trading-day POSITION (1, 2, 3…), not calendar
 * dates — the source tool has no reliable per-row date. Do not relabel as dates.
 */
export default function CandlestickPlusVolume({ chart }: { chart: CandlestickPlusVolumeChart }) {
  const data = useMemo(() => {
    const { open, high, low, close } = chart.candlestick
    return [
      {
        type: 'candlestick',
        name: 'Price',
        x: chart.x_axis,
        open,
        high,
        low,
        close,
        increasing: { line: { color: UP, width: 1 }, fillcolor: UP },
        decreasing: { line: { color: DOWN, width: 1 }, fillcolor: DOWN },
        yaxis: 'y',
      },
      {
        type: 'bar',
        name: 'Volume',
        x: chart.x_axis,
        y: chart.volume,
        marker: { color: INK.neutralMark },
        yaxis: 'y2',
        hovertemplate: 'Volume: %{y:,.0f}<extra></extra>',
      },
    ]
  }, [chart])

  if (chart.x_axis.length === 0) return <EmptyChart message="No price history available." />

  return (
    <Panel
      caption="Price (top) · Volume (bottom)"
      data={data}
      height={380}
      layout={baseLayout({
        showlegend: false,
        hovermode: 'x unified',
        bargap: 0.1,
        xaxis: axis({
          rangeslider: { visible: false },
          title: { text: 'Trading Day', font: { color: INK.muted, size: 11 } },
        }),
        yaxis: axis({ domain: [0.3, 1] }),
        yaxis2: axis({ domain: [0, 0.2], showgrid: false, tickformat: '.2s' }),
      })}
    />
  )
}
