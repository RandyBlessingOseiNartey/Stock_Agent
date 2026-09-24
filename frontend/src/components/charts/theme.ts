// Chart palette and chrome.
//
// SERIES: categorical, assigned in this fixed order and never cycled. Slot 1
// is the brand's Electric Blue; slots 2–5 are the dataviz reference dark-mode
// steps. Validated as a set (dataviz validate_palette.js --mode dark) against
// #111111, #242424 and #1a1a19 — all checks pass: lightness band, chroma
// floor, adjacent CVD ΔE ≥ 8.4, normal-vision ΔE ≥ 19.3, contrast ≥ 3:1.
// No chart shape here needs more than five series.
export const SERIES = ['#2F6BFF', '#d95926', '#199e70', '#c98500', '#d55181'] as const

// Status (reserved meaning — always paired with an icon + label).
export const STATUS = { good: '#0ca30c', warning: '#fab219', critical: '#d03b3b' } as const

export const INK = {
  primary: '#FFFFFF',
  secondary: 'rgba(255,255,255,0.72)',
  muted: 'rgba(255,255,255,0.5)',
  grid: 'rgba(255,255,255,0.08)',
  axis: 'rgba(255,255,255,0.18)',
  neutralMark: 'rgba(255,255,255,0.34)',
}

export const SURFACE = '#242424' // --sa-charcoal: chart cards sit on this

const FONT = "'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif"

/** Shared base layout: transparent ground, recessive grid, brand type. */
export function baseLayout(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    autosize: true,
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { family: FONT, color: INK.secondary, size: 12 },
    margin: { l: 52, r: 16, t: 12, b: 40 },
    hoverlabel: {
      bgcolor: '#111111',
      bordercolor: 'rgba(255,255,255,0.18)',
      font: { family: FONT, color: INK.primary, size: 12 },
    },
    legend: {
      orientation: 'h',
      x: 0,
      xanchor: 'left',
      y: -0.18,
      yanchor: 'top',
      font: { color: INK.secondary, size: 12 },
    },
    xaxis: axis(),
    yaxis: axis({ zeroline: true }),
    bargap: 0.28,
    bargroupgap: 0.08,
    ...overrides,
  }
}

export function axis(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    gridcolor: INK.grid,
    linecolor: INK.axis,
    zerolinecolor: INK.axis,
    tickfont: { color: INK.muted, size: 11 },
    title: { font: { color: INK.muted, size: 11 } },
    automargin: true,
    fixedrange: true, // no accidental zoom while scrolling a report
    ...overrides,
  }
}

export const PLOT_CONFIG = { displayModeBar: false, responsive: true } as const

/** Series keys in a block, excluding the `unit` metadata field. */
export function seriesEntries(block: Record<string, unknown> | undefined): [string, (number | null)[]][] {
  if (!block) return []
  return Object.entries(block).filter(
    (entry): entry is [string, (number | null)[]] => entry[0] !== 'unit' && Array.isArray(entry[1]),
  )
}
