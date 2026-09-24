import { Plot } from './plot'
import { PLOT_CONFIG } from './theme'

interface PanelProps {
  data: unknown[]
  layout: Record<string, unknown>
  height: number
  /** Unit caption shown above the plot, e.g. "USD Billions". */
  caption?: string
}

/** One Plotly plot with a fixed height and an optional unit caption. */
export function Panel({ data, layout, height, caption }: PanelProps) {
  return (
    <div className="chart-panel">
      {caption && <p className="chart-panel__caption">{caption}</p>}
      <Plot
        data={data}
        layout={layout}
        config={PLOT_CONFIG}
        useResizeHandler
        style={{ width: '100%', height }}
      />
    </div>
  )
}

/** Clean "nothing to chart" state — never an empty set of axes. */
export function EmptyChart({ message }: { message: string }) {
  return <p className="chart-empty">{message}</p>
}
