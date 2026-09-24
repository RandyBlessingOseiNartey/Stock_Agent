import Plotly from 'plotly.js/lib/core'
import bar from 'plotly.js/lib/bar'
import candlestick from 'plotly.js/lib/candlestick'
import indicator from 'plotly.js/lib/indicator'
import pie from 'plotly.js/lib/pie'
import scatter from 'plotly.js/lib/scatter'
import scatterpolar from 'plotly.js/lib/scatterpolar'
import createPlotlyComponent from 'react-plotly.js/factory'

// A custom Plotly bundle with only the six trace types our chart shapes
// use, instead of the full ~3.5 MB distribution.
Plotly.register([bar, candlestick, indicator, pie, scatter, scatterpolar])

export const Plot = createPlotlyComponent(Plotly)
