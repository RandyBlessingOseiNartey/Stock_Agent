import type { ResponseStyle, RiskAppetite } from './types'

const ACRONYMS: Record<string, string> = { dcf: 'DCF' }

/** `competitive_benchmarking` → "Competitive Benchmarking", `dcf` → "DCF". */
export function analysisLabel(key: string): string {
  return key
    .split('_')
    .map((word) => ACRONYMS[word] ?? word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

const TOOL_LABELS: Record<string, string> = {
  resolve_ticker_symbol: 'Resolving ticker symbol',
  get_income_statement: 'Income statement',
  get_balance_sheet: 'Balance sheet',
  get_cash_flow: 'Cash flow statement',
  get_company_overview: 'Company overview',
  get_key_metrics: 'Key metrics',
  get_stock_quote: 'Stock quote',
  get_price_history: 'Price history',
  get_share_statistics: 'Share statistics',
  get_stock_peers: 'Peer companies',
  get_dividend_history: 'Dividend history',
  tavily: 'Web & news search',
  generate_chart: 'Preparing chart',
}

/** Human label for a tool name; falls back to the raw name for unknown tools. */
export function toolLabel(tool: string): string {
  return TOOL_LABELS[tool] ?? tool
}

export const RESPONSE_STYLE_OPTIONS: { value: ResponseStyle; label: string; hint: string }[] = [
  { value: 'precise', label: 'Precise', hint: 'Most consistent, numbers-first' },
  { value: 'balanced', label: 'Balanced', hint: 'Default' },
  { value: 'exploratory', label: 'Exploratory', hint: 'Broader, more open-ended' },
]

export const RISK_APPETITE_OPTIONS: { value: RiskAppetite; label: string; hint: string }[] = [
  { value: 'conservative', label: 'Conservative', hint: 'Capital preservation first' },
  { value: 'moderate', label: 'Moderate', hint: 'Balanced growth & preservation' },
  { value: 'aggressive', label: 'Aggressive', hint: 'Maximum growth' },
]

let counter = 0
/** Cheap unique id for React keys within one page session. */
export function uid(prefix = 'id'): string {
  counter += 1
  return `${prefix}-${counter}`
}
