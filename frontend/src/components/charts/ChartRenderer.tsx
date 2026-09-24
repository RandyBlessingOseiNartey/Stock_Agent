import type { ChartSpec } from '../../lib/types'
import BulletRange from './BulletRange'
import CandlestickPlusVolume from './CandlestickPlusVolume'
import ComboBarLine from './ComboBarLine'
import DividendBar from './DividendBar'
import DonutPlusGauge from './DonutPlusGauge'
import GaugeSetPlusRadar from './GaugeSetPlusRadar'
import GroupedBarPlusLine from './GroupedBarPlusLine'
import HorizontalBar from './HorizontalBar'
import { EmptyChart } from './Panel'
import StackedBarPlusLine from './StackedBarPlusLine'

function renderChart(chart: ChartSpec) {
  switch (chart.chart_type) {
    case 'grouped_bar_plus_line':
      return <GroupedBarPlusLine chart={chart} />
    case 'stacked_bar_plus_line':
      return <StackedBarPlusLine chart={chart} />
    case 'combo_bar_line':
      return <ComboBarLine chart={chart} />
    case 'gauge_set_plus_radar':
      return <GaugeSetPlusRadar chart={chart} />
    case 'horizontal_bar':
      return <HorizontalBar chart={chart} />
    case 'bullet_range':
      return <BulletRange chart={chart} />
    case 'candlestick_plus_volume':
      return <CandlestickPlusVolume chart={chart} />
    case 'donut_plus_gauge':
      return <DonutPlusGauge chart={chart} />
    case 'bar':
      return <DividendBar chart={chart} />
    default:
      return <EmptyChart message="This chart type isn't supported yet." />
  }
}

/** Maps a chart_type to its component. Error isolation lives in ChartCard. */
export default function ChartRenderer({ chart }: { chart: ChartSpec }) {
  return renderChart(chart)
}
