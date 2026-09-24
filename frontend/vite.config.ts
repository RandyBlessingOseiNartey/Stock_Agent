import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import svgr from 'vite-plugin-svgr'

export default defineConfig({
  // svgr turns `*.svg?react` imports into inline React components — the
  // brand loader's animation lives in embedded CSS @keyframes, which only
  // run when the SVG is part of the DOM (never through <img> or CSS url()).
  plugins: [react(), svgr()],
  // plotly.js's per-trace CommonJS sources reference Node's `global`.
  define: { global: 'globalThis' },
  build: {
    // The one large chunk is the custom Plotly bundle (components/charts),
    // already lazy-loaded on first chart render. Everything else is small.
    chunkSizeWarningLimit: 1400,
  },
  server: {
    port: 5173,
    proxy: {
      // Proxying keeps the browser on one origin, so SSE requests are
      // same-origin and CORS never enters the picture during development.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
