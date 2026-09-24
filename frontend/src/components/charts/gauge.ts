import type { GaugeSpec } from '../../lib/types'
import { INK, STATUS } from './theme'

type Band = 'good' | 'fair' | 'weak'

const BAND_STYLE: Record<Band, { color: string; icon: string; label: string }> = {
  good: { color: STATUS.good, icon: '✓', label: 'Good' },
  fair: { color: STATUS.warning, icon: '~', label: 'Fair' },
  weak: { color: STATUS.critical, icon: '!', label: 'Weak' },
}

const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)

function withAlpha(hex: string, alpha: number): string {
  const n = parseInt(hex.slice(1), 16)
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`
}

/**
 * Turns a benchmark spec into gauge bands. `good_max` set → lower is better
 * (P/E, Debt/Equity, short interest); otherwise `good_min` → higher is
 * better (Current Ratio, ROE). Returns null when there are no thresholds.
 */
function bands(g: GaugeSpec, lo: number, hi: number) {
  if (isNum(g.good_max)) {
    const fairMax = isNum(g.fair_max) ? g.fair_max : g.good_max
    return [
      { band: 'good' as Band, range: [lo, g.good_max] },
      { band: 'fair' as Band, range: [g.good_max, fairMax] },
      { band: 'weak' as Band, range: [fairMax, hi] },
    ]
  }
  if (isNum(g.good_min)) {
    const fairMin = isNum(g.fair_min) ? g.fair_min : g.good_min
    return [
      { band: 'weak' as Band, range: [lo, fairMin] },
      { band: 'fair' as Band, range: [fairMin, g.good_min] },
      { band: 'good' as Band, range: [g.good_min, hi] },
    ]
  }
  return null
}

/**
 * One Plotly bullet-gauge indicator trace for a benchmarked metric. The
 * verdict (Good / Fair / Weak) is spelled out with an icon in the title —
 * the band color never carries the meaning on its own.
 */
export function gaugeTrace(g: GaugeSpec, domain: { x: [number, number]; y: [number, number] }) {
  const thresholds = [g.good_min, g.good_max, g.fair_min, g.fair_max].filter(isNum)
  const top = Math.max(g.value, ...thresholds, 0)
  const hi = top > 0 ? top * 1.3 : 1
  const lo = Math.min(0, g.value * 1.15)
  const bandList = bands(g, lo, hi)

  const verdict = bandList?.find(({ range: [a, b] }) => g.value >= a && g.value <= b)?.band
  const style = verdict ? BAND_STYLE[verdict] : null
  const suffix = g.unit === '%' ? '%' : ''

  return {
    type: 'indicator',
    mode: 'number+gauge',
    value: g.value,
    domain,
    number: { suffix, font: { size: 17, color: INK.primary }, valueformat: '.2~f' },
    title: {
      text: style
        ? `${g.metric}<br><span style="font-size:11px;color:${INK.muted}">${style.icon} ${style.label}</span>`
        : g.metric,
      font: { size: 13, color: INK.secondary },
    },
    gauge: {
      shape: 'bullet',
      axis: { range: [lo, hi], tickfont: { size: 10, color: INK.muted }, tickcolor: INK.axis },
      bar: { color: INK.primary, thickness: 0.32 },
      bgcolor: 'rgba(255,255,255,0.04)',
      borderwidth: 0,
      steps: (bandList ?? []).map(({ band, range }) => ({ range, color: withAlpha(BAND_STYLE[band].color, 0.3) })),
    },
  }
}
