import { toolLabel } from '../../lib/labels'
import type { TraceItem } from '../../lib/types'

interface ToolTraceProps {
  items: TraceItem[]
  /** Collapsed by default once the run is over; open while it's live. */
  live: boolean
  retry?: { attempt: number; max_retries: number } | null
}

/**
 * The live "reasoning trace": one row per data-tool call. Deliberately
 * static glyphs (→ running, ✓ done) — the BrandLoader is the only moving
 * loading indicator in the app.
 */
export function ToolTrace({ items, live, retry }: ToolTraceProps) {
  if (items.length === 0 && !retry) return null
  const done = items.filter((i) => i.status === 'done').length
  const summary = live
    ? `Gathering data · ${done}/${items.length} tools complete`
    : `Used ${items.length} data ${items.length === 1 ? 'tool' : 'tools'}`

  return (
    // `key` flips on live → done so the <details> re-mounts with the new default.
    <details className="trace" open={live} key={live ? 'live' : 'done'}>
      <summary className="trace__summary">{summary}</summary>
      {retry && (
        <p className="trace__retry" role="status">
          Model returned an empty response. Retrying (attempt {retry.attempt} of {retry.max_retries})…
        </p>
      )}
      <ol className="trace__list">
        {items.map((item) => (
          <li key={item.id} className={`trace__item trace__item--${item.status}`}>
            <span className="trace__glyph" aria-hidden="true">
              {item.status === 'done' ? '✓' : '→'}
            </span>
            <span className="trace__label">
              {item.status === 'done' ? toolLabel(item.tool) : `Calling ${toolLabel(item.tool)}…`}
            </span>
            <code className="trace__tool">{item.tool}</code>
          </li>
        ))}
      </ol>
    </details>
  )
}
