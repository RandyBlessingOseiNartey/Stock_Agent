# frontend — React + TypeScript + Vite

The StockAgent UI. Chat is the default view; a tab bar switches modes. See the
[root README](../README.md) for setup and the whole system; this file covers
the frontend specifically.

```bash
npm install
npm run dev      # http://localhost:5173 (proxies /api → localhost:8000)
npm run build    # tsc -b + vite build
npm run lint     # oxlint
```

```
src/
├── App.tsx                 mode tabs; all three modes stay mounted
├── modes/                  ChatMode · TerminalMode · DeepResearchMode
├── components/
│   ├── brand/              BrandLoader, WorkingMark, LoaderStage, Wordmark
│   ├── composer/           Composer shell, Dropdown, one composer per mode
│   ├── stream/             ToolTrace, Report, ChartCard, ErrorState
│   └── charts/             one component per chart_type + Plotly bundle
├── lib/                    sse.ts, useStreamController.ts, types.ts, api.ts
└── styles/                 tokens.css (brand values) · app.css
```

**All three modes stay mounted** and are only hidden when inactive, so
switching tabs never kills an in-flight stream or loses a finished report.

## Consuming the streams

Native `EventSource` can't do POST bodies or custom headers, and every stream
endpoint is a POST (Chat also needs `X-User-Id`). So `lib/sse.ts` uses
[`@microsoft/fetch-event-source`](https://github.com/Azure/fetch-event-source)
with two non-obvious settings:

- **`openWhenHidden: true`** — without it the library closes the stream when
  the tab is hidden and silently re-POSTs on return, starting a *duplicate
  agent run* on the server.
- **Rethrow in `onerror`** — stops automatic reconnection. Every error is
  terminal for that request.

`useStreamController` owns one in-flight stream per mode, aborts the previous
one when a new starts (or on unmount), and **batches events into one flush per
animation frame** — a burst of tokens causes one React render instead of
dozens, which matters because each render re-parses the growing markdown.

## The brand mark

`BRAND_MARK_SIZE` in `components/brand/BrandLoader.tsx` is the single source of
truth for mark size — **no call site passes its own**. `WorkingMark` animates
for the whole run (tool events *and* token streaming) and cross-fades in place
to the static bolt when the run ends. Both states sit in one fixed-size slot,
so the swap costs zero layout shift, and it's the only loading indicator in the
app.

Two things about `stockagent-loader.svg` in `components/brand/` — it differs
deliberately from the pristine asset in `public/brand/`, and both differences
are commented in the file:

1. Its nested `<svg>` is flattened to a `<g transform>`. **SVGR spreads the
   component's props onto every `<svg>` it finds**, so `width`/`height` also
   hit the inner one and shrank the bolt to 32% of its intended size.
2. Resting opacity is `.42` instead of `.20`, which otherwise left the bolt
   near-invisible for about half of each 2-second cycle.

## Charts

`components/charts/plot.ts` builds a **custom Plotly bundle** with only the six
trace types used (bar, candlestick, indicator, pie, scatter, scatterpolar)
instead of the ~3.5 MB full distribution, and `ChartCard` lazy-loads it on the
first chart. `vite.config.ts` sets `define: { global: 'globalThis' }` because
Plotly's CommonJS sources reference Node's `global`.

The palette in `charts/theme.ts` is validated for colorblind safety against the
brand's dark surfaces; slot 1 is the brand accent. Series colors are assigned in
fixed order and never cycled, and no chart uses two y-scales — the income
statement renders as two stacked panels (USD and %) rather than a dual axis.

A failed chart is isolated by an error boundary **around** the lazy import, so
a bad payload or a failed chunk load costs that one chart, never the report.

## Dev-only auth

`lib/api.ts` sends a fixed placeholder `X-User-Id` matching the backend stub.
Override with `VITE_USER_ID` in `frontend/.env.local`. This is not
authentication — replace before deploying.
