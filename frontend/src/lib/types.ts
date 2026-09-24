// Mirrors the event vocabularies in BACKEND_FASTAPI.md §4 and the chart
// shapes produced by each feature's chart_data.py. Keep these in sync with
// the Python side — they are the wire contract.

export type ResponseStyle = 'precise' | 'balanced' | 'exploratory'
export type RiskAppetite = 'conservative' | 'moderate' | 'aggressive'

// ── Charts ─────────────────────────────────────────────────────────

/** A "series block": named numeric arrays plus an optional `unit` string. */
export type SeriesBlock = { unit?: string } & Record<string, (number | null)[] | string | undefined>

export interface GroupedBarPlusLineChart {
  chart_type: 'grouped_bar_plus_line'
  title: string
  x_axis: string[]
  bar_series: SeriesBlock
  line_series: SeriesBlock
}

export interface StackedBarPlusLineChart {
  chart_type: 'stacked_bar_plus_line'
  title: string
  x_axis: string[]
  stacked_bar_series: SeriesBlock
  stacked_bar_series_liabilities?: SeriesBlock
  line_series: SeriesBlock
}

export interface ComboBarLineChart {
  chart_type: 'combo_bar_line'
  title: string
  x_axis: string[]
  bar_series: SeriesBlock
  line_series: SeriesBlock
}

export interface GaugeSpec {
  metric: string
  value: number
  /** "%" for percent metrics (value and bands already x100). */
  unit?: string | null
  good_min?: number | null
  good_max?: number | null
  fair_min?: number | null
  fair_max?: number | null
  days_to_cover?: number | null
}

export interface GaugeSetPlusRadarChart {
  chart_type: 'gauge_set_plus_radar'
  title: string
  gauges: GaugeSpec[]
  radar: { unit?: string; values: Record<string, number> }
}

export interface HorizontalBarChart {
  chart_type: 'horizontal_bar'
  title: string
  unit?: string
  entries: { symbol: string | null; market_cap_b: number; is_subject: boolean }[]
}

export interface BulletRangeChart {
  chart_type: 'bullet_range'
  title: string
  unit?: string
  range_low: number | null
  range_high: number | null
  current_value: number | null
  markers: Record<string, number | null>
}

export interface CandlestickPlusVolumeChart {
  chart_type: 'candlestick_plus_volume'
  title: string
  x_axis: number[]
  x_axis_label?: string
  candlestick: { open: (number | null)[]; high: (number | null)[]; low: (number | null)[]; close: (number | null)[] }
  volume: (number | null)[]
}

export interface DonutPlusGaugeChart {
  chart_type: 'donut_plus_gauge'
  title: string
  donut: Record<string, number>
  gauge: GaugeSpec
}

export interface BarChart {
  chart_type: 'bar'
  title: string
  x_axis: string[]
  values: number[]
  note?: string
}

export type ChartSpec =
  | GroupedBarPlusLineChart
  | StackedBarPlusLineChart
  | ComboBarLineChart
  | GaugeSetPlusRadarChart
  | HorizontalBarChart
  | BulletRangeChart
  | CandlestickPlusVolumeChart
  | DonutPlusGaugeChart
  | BarChart

/** A chart slot as it arrives on the wire: either a spec or a per-chart error. */
export interface ChartItem {
  id: string
  tool?: string
  chart?: ChartSpec
  error?: string
}

// ── Stream events ──────────────────────────────────────────────────

interface ToolEvent { type: 'tool_start' | 'tool_end'; tool: string }
interface RetryEvent { type: 'retry'; attempt: number; max_retries: number }
interface ChartEvent { type: 'chart'; tool?: string; chart?: ChartSpec; error?: string }
interface TokenEvent { type: 'token'; content: string }

export type DeepResearchEvent = (
  | { type: 'stage'; status: 'start' | 'end' }
  | ToolEvent
  | RetryEvent
  | ChartEvent
  | { type: 'retriever_done' | 'retriever_failed'; content: string }
  | TokenEvent
  | { type: 'brief_done'; content: string }
  | { type: 'failed'; content: string }
) & { stage?: 'retriever' | 'investment_brief' }

export type TerminalEvent =
  | ToolEvent
  | RetryEvent
  | ChartEvent
  | TokenEvent
  | { type: 'done' | 'failed'; content: string }

export type ChatEvent =
  | { type: 'conversation_created'; conversation_id: string }
  | ToolEvent
  | RetryEvent
  | ChartEvent
  | TokenEvent
  | { type: 'title_generated'; conversation_id: string; title: string }
  | { type: 'done' | 'failed'; conversation_id?: string; content: string }

// ── Trace ──────────────────────────────────────────────────────────

export interface TraceItem {
  id: string
  tool: string
  status: 'running' | 'done'
}

// ── REST payloads ──────────────────────────────────────────────────

export interface AnalysisInfo {
  key: string
  description: string
  tools: string[]
}

export interface ConversationSummary {
  id: string
  title: string | null
  updated_at: string | null
}

export interface StoredMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string | null
}
