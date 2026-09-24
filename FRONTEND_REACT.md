# StockAgent — Frontend (React) Implementation Guide

Read `PROJECT_CONTEXT.md` and `BACKEND_FASTAPI.md` first. This document
covers UI structure, the brand system, and exactly how to consume the
backend's SSE streams.

---

## 1. Overall UI Structure

**Chat is the main interface and the default view on load.** A **Modes**
tab/switcher lets the user move between the three features:

```
┌─────────────────────────────────────────┐
│  [Chat]  [Terminal]  [Deep Research]     │  ← Modes tab, Chat active by default
├─────────────────────────────────────────┤
│                                           │
│         (mode-specific content)          │
│                                           │
├─────────────────────────────────────────┤
│         (mode-specific composer)         │
└─────────────────────────────────────────┘
```

Each mode is treated as an independent view — they do not share
conversation/report state with each other (only the auth header is
shared across all three, per `BACKEND_FASTAPI.md` Section 2).

### 1.1 Chat Mode (default)
Standard ChatGPT-style layout: a sidebar listing past conversations
(from `GET /api/chat/conversations`), the active conversation's message
history in the main pane, and the composer at the bottom.

### 1.2 Terminal Mode
On entering this mode, **do not show a composer immediately.** Instead,
show a grid of **12 clickable cards**, one per analysis agent, built from
`GET /api/terminal/analyses`:

```
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│  Income  │ │ Balance  │ │   Cash   │ │Liquidity │
│Statement │ │  Sheet   │ │   Flow   │ │          │
└──────────┘ └──────────┘ └──────────┘ └──────────┘
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ Solvency │ │Profitab- │ │Valuation │ │   DCF    │
│          │ │  ility   │ │          │ │          │
└──────────┘ └──────────┘ └──────────┘ └──────────┘
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│  Growth  │ │Volatility│ │Sentiment │ │Competitive│
│          │ │          │ │          │ │Benchmark │
└──────────┘ └──────────┘ └──────────┘ └──────────┘
```

Each card shows the agent's name (derive a display label from its `key`,
e.g. `dcf` → "DCF", `competitive_benchmarking` → "Competitive
Benchmarking") and its `description` field from the API response.

**Clicking a card reveals that agent's composer** (input + Response Style
dropdown + Send — see Section 3.2) and the output pane, replacing the
card grid. Provide a clear "← Back" affordance to return to the grid.
This two-step flow (pick an agent, then get its composer) is a deliberate
simplicity decision — do not try to cram all 12 agents' inputs into one
screen.

### 1.3 Deep Research Mode
Single composer (Section 3.1), single output pane below it. No card
selection step needed — Deep Research is one pipeline, not 12.

---

## 2. Brand System

**Use these values exactly. Do not approximate, substitute, or invent
alternatives.**

### 2.1 Colors

```css
--sa-black: #111111;      /* primary dark surface */
--sa-charcoal: #242424;   /* secondary dark surface */
--sa-white: #FFFFFF;      /* light surface */
--sa-accent: #2F6BFF;     /* Electric Blue — CTAs, active states, loader flash ONLY */
```

`--sa-accent` is used **sparingly** — never as a dominant UI color. It
appears on: primary CTA buttons, active/selected states (e.g. the active
Modes tab, a selected dropdown option), and the loader's flash moment.

### 2.2 Typography

Wordmark and headings: **Space Grotesk**, weights 400/500/600/700
(self-host if the project already self-hosts fonts, otherwise via Google
Fonts). Wordmark specifically uses weight 600 with `letter-spacing: -0.025em`.

```css
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap');

.wordmark {
  font-family: 'Space Grotesk', -apple-system, sans-serif;
  font-weight: 600;
  letter-spacing: -0.025em;
  line-height: 1;
}
```

### 2.3 Logo / Symbol

The symbol is a bolt made of two identical parallelograms (a "double
parallelogram" construction, all four edges at a consistent −12:34 angle,
symmetric 12px notch offset on each side):

```html
<svg viewBox="0 0 56 84" xmlns="http://www.w3.org/2000/svg">
  <polygon points="47,8 21,8 9,42 21,42 9,76 35,76 47,42 35,42" shape-rendering="geometricPrecision"/>
</svg>
```
(`fill: currentColor` — this is what makes it a "polygon" element you can
recolor via CSS `color`, as in the brand sheet.)

**Usage rules:**
- App icon / favicon: symbol only, no wordmark, on `--sa-black` background.
- Light backgrounds: use the reversed lockup (dark bolt + dark wordmark) — never place a light-colored bolt on a light surface.
- Full lockup (bolt + "StockAgent" wordmark) for headers/nav.
- Accent variant: bolt in `--sa-black`/white, wordmark styled as `Stock` + `<span style="color: var(--sa-accent)">Agent</span>` — the split-color wordmark treatment shown in the brand sheet's "accent" example. Use this sparingly, e.g. a splash/landing moment — not as the default persistent header treatment.

Place all brand SVGs under `/public/brand/`.

### 2.4 BrandLoader Component

**This is the only loading indicator anywhere in the app.** Remove every
existing/default spinner, browser-native loading state, or third-party
spinner library usage across all three modes before considering this done.

Build one reusable component:

```tsx
// components/brand/BrandLoader.tsx
interface BrandLoaderProps {
  size?: number;       // pixels, default 48
  className?: string;  // for layout positioning by the parent
}
```

- Renders the inline contents of the provided `stockagent-loader.svg`
  (import as an inline SVG component / via SVGR — **not** an `<img>` tag
  or CSS `background-image`, since the animation is driven by embedded
  CSS `@keyframes` that do not execute through either of those).
- No accompanying spinner ring, no baked-in loading text. It is a
  complete, self-sufficient indicator on its own.
- Default bolt fill is white — on light backgrounds, wrap it in a dark
  scrim (`--sa-black` or `--sa-charcoal` rounded container) rather than
  placing it directly on a light surface.

**Wire it into every request lifecycle identically across all three
modes:**

1. Show `<BrandLoader />` the instant a request is dispatched (Send
   clicked, card clicked and its first load triggered, etc.).
2. Because everything streams via SSE, follow this exact sequence:
   - Loader shows from dispatch until the **first** event of any kind
     arrives (first `tool_start`, or first `token` if a feature/run
     happens to call no tools).
   - On that first event, **fade** the loader out (do not hard-remove
     it) and hand off to the streaming UI (tool trace, chart panels,
     live-typing text).
   - If the stream errors or the connection drops before any event
     arrives, replace the loader with the app's error state — never
     leave it spinning indefinitely.
3. Add a minimum display time of roughly 200–300ms (debounce) so it
   never flashes for under ~100ms on a very fast response — that reads
   as a glitch, not a loading state.
4. Reserve the loader's layout space before it mounts — zero layout
   shift on mount/unmount.

**Placement per mode:**
- **Chat**: small (24–32px), positioned where the next assistant message
  will render — this replaces any typing-indicator concept entirely.
- **Terminal**: renders inside the output pane the selected agent's
  response will stream into.
- **Deep Research**: renders where the investment brief will appear;
  pair with existing status copy (e.g. "Retrieving sources...") in the
  standard body font, positioned so it doesn't visually compete with the
  bolt animation itself.

**Before considering brand integration done:** confirm 60fps animation
on all three surfaces, grep the codebase to confirm zero leftover spinner
libraries/classes remain, confirm exact hex values and Space Grotesk are
used with no fallback substitutions, and confirm the identical
`BrandLoader` component (not a per-feature variant) is used in all three
places.

---

## 3. Composer / Toolbar Specs

All three composers follow the same visual language: a text input with
one or two dropdown buttons and a Send button in the same toolbar row —
selections are made in the same input area the user types into, not in a
separate settings panel.

### 3.1 Deep Research Composer

```
┌────────────────────────────────────────────────────────────┐
│  [ Enter a company name or ticker...                    ]  │
│  [Risk Appetite ▾]        [Response Style ▾]      [Send →] │
└────────────────────────────────────────────────────────────┘
```
- Text input: free-form query (company name, ticker, or a natural
  question — the retriever agent handles resolution).
- **Risk Appetite dropdown**: `Conservative` / `Moderate` / `Aggressive`, default **Moderate**.
- **Response Style dropdown**: `Precise` / `Balanced` / `Exploratory`, default **Balanced**.
- Send → `POST /api/deep-research/stream` with `{ query, response_style, risk_appetite }`.

### 3.2 Terminal Composer (per selected agent card)

```
┌────────────────────────────────────────────────────────────┐
│  [ Enter a company name or ticker...                    ]  │
│                            [Response Style ▾]      [Send →] │
└────────────────────────────────────────────────────────────┘
```
- **No Risk Appetite dropdown** — Terminal agents don't accept that
  parameter.
- Response Style dropdown: same three options, default Balanced.
- Send → `POST /api/terminal/stream` with `{ analysis_type: <selected card's key>, company_input, response_style }`.

### 3.3 Chat Composer

```
┌────────────────────────────────────────────────────────────┐
│  [ Ask about any company, comparison, or strategy...    ]  │
│                            [Response Style ▾]      [Send →] │
└────────────────────────────────────────────────────────────┘
```
- No Risk Appetite dropdown (Chat has no such parameter).
- Response Style dropdown: same three options, default Balanced.
- Send → `POST /api/chat/stream` with `{ conversation_id, message, response_style }`. Include a "+ New Chat" affordance (likely in the sidebar) that resets `conversation_id` to `null` for the next send.

---

## 4. Consuming SSE Streams

Native `EventSource` only supports `GET` requests with no custom body or
headers — insufficient here, since every stream endpoint is a `POST`
carrying a JSON body (and Chat also needs the `X-User-Id` header). Use
`fetch()` with a `ReadableStream` reader instead, or the small
`@microsoft/fetch-event-source` library, which supports POST bodies,
custom headers, and reconnection out of the box.

**Recommended: `@microsoft/fetch-event-source`.**

```tsx
import { fetchEventSource } from '@microsoft/fetch-event-source';

async function streamDeepResearch(
  query: string,
  responseStyle: string,
  riskAppetite: string,
  handlers: {
    onEvent: (event: any) => void;
    onError: (err: unknown) => void;
    onDone: () => void;
  }
) {
  await fetchEventSource('/api/deep-research/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, response_style: responseStyle, risk_appetite: riskAppetite }),
    onmessage(msg) {
      const event = JSON.parse(msg.data);
      handlers.onEvent(event);
    },
    onerror(err) {
      handlers.onError(err);
      throw err; // stop the library's automatic retry — this is a terminal error for this request
    },
    onclose() {
      handlers.onDone();
    },
  });
}
```

Apply the same pattern for Terminal (`/api/terminal/stream`) and Chat
(`/api/chat/stream`, remembering to add the `X-User-Id` header and to
capture `conversation_id` from the `conversation_created` event on a
fresh conversation).

### 4.1 Event Handling Rules (apply per mode's own vocabulary — see `BACKEND_FASTAPI.md` Section 4)

| Event type | UI behavior |
|---|---|
| `tool_start` / `tool_end` | Append/update a line in a live "reasoning trace" list (e.g. "🔧 Calling get_income_statement…" → "✓ get_income_statement completed"). |
| `retry` | Show a small inline "Retrying…" indicator; the trace list will replay from the top as the tool calls re-fire. |
| `chart` (has `chart` key) | Render via the chart component matching `chart.chart_type` (Section 5). Timing differs by mode — see below. |
| `chart` (has `error` key instead) | Show a small inline "chart unavailable" note — never block or fail the whole response over one missing chart. |
| `token` | Append to the currently-streaming text block, live. |
| `done` / `brief_done` | Finalize the message — stop showing any "streaming" indicator, allow the next composer submission. |
| `failed` / `retriever_failed` | Show the app's standard error state with the message from `content` — this is already a human-readable message, not a raw stack trace. |
| `title_generated` (Chat only) | Update the sidebar's conversation title in place — no page reload. |
| `conversation_created` (Chat only) | Store the returned `conversation_id` for this session's subsequent sends. |

**Chart timing per mode** (matches how each backend actually emits them —
see `PROJECT_CONTEXT.md` Section 4):
- **Deep Research**: chart events arrive as a batch right after the
  `stage: retriever, status: end` event and before any `token` events
  begin — render all of them above/alongside the report output area
  before the report text starts appearing.
- **Terminal**: chart events arrive as a batch right at the moment the
  first `token` event fires — render them above the streaming text panel.
- **Chat**: chart events can arrive at any point during a turn,
  interleaved with tokens — render each one inline within the assistant's
  message bubble at the position it arrived.

---

## 5. Chart Rendering

Use `react-plotly.js`. Map each `chart.chart_type` value to the
appropriate Plotly configuration:

| `chart_type` | Plotly chart | Notes |
|---|---|---|
| `grouped_bar_plus_line` | Grouped bar (`bar_series`) + line overlay (`line_series`) | Income statement: revenue/profit bars + margin % line |
| `stacked_bar_plus_line` | Stacked bar + line | Balance sheet composition + working capital/net debt trend |
| `combo_bar_line` | Bar (OCF/CapEx) + line (FCF) | Cash flow |
| `gauge_set_plus_radar` | One gauge per entry in `gauges[]`, plus one radar chart from `radar.values` | Key metrics — gauge bands come from each entry's `good_min`/`good_max`/`fair_min`/`fair_max` |
| `horizontal_bar` | Horizontal bar, from `entries[]` (each has `symbol`, `market_cap_b`, `is_subject`) | Peer comparison — visually distinguish the `is_subject: true` entry (e.g. accent color) |
| `bullet_range` | Bullet/range chart: `range_low` to `range_high`, marker at `current_value`, additional markers from `markers{}` | Stock quote / 52-week position |
| `candlestick_plus_volume` | Candlestick (`candlestick.open/high/low/close`) + volume bars beneath, x-axis from `x_axis` (positional integers — label the axis "Trading Day", not calendar dates) | Price history |
| `donut_plus_gauge` | Donut (`donut{}`) + one gauge (`gauge{}`) | Share statistics — ownership split + short interest |
| `bar` | Simple bar (`x_axis`, `values`) | Dividend history — may be empty for non-dividend-paying companies; render a clean "No dividend history" state, not an empty chart |

Every chart response includes a `title` field — use it as the chart's
heading. Some include a `unit` field (e.g. "USD Billions", "Percent") —
show it in the axis label or a small caption.

---

## 6. Suggested Frontend Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── brand/
│   │   │   └── BrandLoader.tsx
│   │   ├── charts/           (one component per chart_type from Section 5)
│   │   ├── composer/
│   │   │   ├── DeepResearchComposer.tsx
│   │   │   ├── TerminalComposer.tsx
│   │   │   └── ChatComposer.tsx
│   │   └── ...
│   ├── modes/
│   │   ├── ChatMode.tsx
│   │   ├── TerminalMode.tsx      (card grid + selected-agent view)
│   │   └── DeepResearchMode.tsx
│   ├── lib/
│   │   └── sse.ts                (fetchEventSource wrappers per endpoint)
│   └── App.tsx                   (Modes tab switcher, Chat as default)
└── public/
    └── brand/                    (all brand SVGs)
```

---

## 7. Known Gaps to Finish (mirrors `PROJECT_CONTEXT.md` Section 5)

- No real auth UI — the `X-User-Id` header can be hardcoded/stubbed on
  the frontend for now, matching the backend's dev-only stub.
- Chat's conversation list/sidebar UX (rename, delete, archive) beyond
  basic list + open + new-chat is not specified here — treat as a
  reasonable follow-up, not a blocker for this pass.
- Dividend chart rendering should be tested against a real API response
  once `get_dividend_history` is verified server-side (see
  `PROJECT_CONTEXT.md` Section 5) — the field names feeding this chart
  may need adjustment.
