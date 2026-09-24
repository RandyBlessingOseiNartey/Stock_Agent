# Prompt: Integrate StockAgent Brand Identity + Animated Loader

Copy everything below into your coding agent, with the 6 SVG files attached (primary lockup, reversed lockup, symbol, vertical lockup, brand sheet, and loader).

---

## Task

Integrate the StockAgent brand identity system into the frontend. The primary objective is replacing every existing loading/spinner state with the animated brand loader (`stockagent-loader.svg`), specifically during backend request lifecycles across Deep Research, Terminal, and Chat.

## Context

- Backend streams responses via LangChain's `astream_events(v2)` (async event stream, not a single request/response).
- Three independent feature surfaces exist: Deep Research, Terminal, Chat. Each currently has its own request handling and likely its own loading indicator.
- Attached assets:
  1. `stockagent-primary-lockup.svg` (dark background, full lockup)
  2. `stockagent-reversed-lockup.svg` (light background, full lockup)
  3. `stockagent-symbol.svg` (bolt only, for favicon/app icon)
  4. `stockagent-vertical-lockup.svg` (splash screens)
  5. `stockagent-brand-sheet.svg` (reference only, colors and typeface specimen, not for direct UI use)
  6. `stockagent-loader.svg` (animated bolt, this is the file to wire into loading states)

## Step 1: Asset setup

- Place all SVGs under `/public/brand/` (or the project's existing static assets convention).
- The loader must be imported as an inline SVG component or via SVGR, not rendered through an `<img>` tag. The animation is driven by embedded CSS `@keyframes`, which do not execute inside `<img>` or background-image references.
- Register the Space Grotesk font (weights 400, 500, 600, 700), self-hosted if the project already self-hosts fonts, otherwise via Google Fonts.

## Step 2: Design tokens

Add these to the project's existing token system (Tailwind config, CSS variables, or theme file, whichever the codebase already uses):

```
--sa-black: #111111
--sa-charcoal: #242424
--sa-white: #FFFFFF
--sa-accent: #2F6BFF
```

`--sa-accent` is used sparingly: CTAs, active states, and the loader's flash moment only. It is never a dominant UI color.

Font family for the wordmark: `'Space Grotesk'`, weight 600, letter-spacing -0.025em.

## Step 3: Build a reusable loader component

Create a single `BrandLoader` component (e.g., `components/brand/BrandLoader.tsx`):

- Renders the inline contents of `stockagent-loader.svg`.
- Props: `size` (pixels, default 48), `className` (optional, for layout positioning by the parent).
- No accompanying spinner ring, no additional loading text baked into the component. It is a complete, self-sufficient loading indicator.
- The bolt fill is white by default. On light backgrounds, either wrap it in a dark scrim (`--sa-black` or `--sa-charcoal` rounded container) or add a dark-fill variant. Do not place a white bolt directly on a white or light surface.

This must be the only loading indicator used anywhere requests are pending. Remove existing spinners: native browser spinners, third-party spinner libraries, CSS-only loading circles, or any feature-specific one-off loaders currently in Deep Research, Terminal, or Chat.

## Step 4: Wire into the request lifecycle

This is the core task. For each of the three feature surfaces:

1. Identify every point where a request to the backend is dispatched (button click, query submit, agent invocation).
2. Show `<BrandLoader />` immediately when the request is dispatched.
3. Because responses stream via `astream_events(v2)`, follow this exact sequence:
   - Loader displays from request start until the first event/token arrives.
   - On first event, fade the loader out (do not remove it abruptly) and hand off to the existing streaming UI (token-by-token render, agent status updates, etc.).
   - If the stream errors or times out before any event arrives, replace the loader with the app's existing error state. Never leave it spinning indefinitely.
4. Add a minimum display time (roughly 200 to 300ms) or debounce so the loader does not flash on very fast responses. A loader that appears for under 100ms and disappears reads as a UI glitch, not a loading state.
5. Confirm zero layout shift when the loader mounts or unmounts. Reserve the space it will occupy before it appears.

## Step 5: Placement per surface

- **Chat**: small loader (24 to 32px), positioned where the next agent message will render, replacing any existing typing indicator.
- **Terminal**: loader appears inside the output pane that the agent's response streams into.
- **Deep Research**: loader appears where the investment brief will render. Pair it with the existing status copy (e.g., "Retrieving sources...") in the app's standard body font, positioned so it does not visually compete with the bolt.

## Step 6: Confirm before marking this done

- Animation runs at 60fps on all three surfaces, no jank.
- No duplicate or legacy spinners remain anywhere in the codebase (grep for the removed libraries/classes to confirm).
- Exact hex values and font are used, no approximated colors or fallback fonts.
- The same `BrandLoader` component and identical behavior is used across all three surfaces. No feature built its own variant.

## Deliverable

A single reusable `BrandLoader` component wired into all three request flows, plus a summary listing every file touched and every spinner it replaced.
