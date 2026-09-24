/// <reference types="vite/client" />
/// <reference types="vite-plugin-svgr/client" />

interface ImportMetaEnv {
  /** Optional override for the dev-only X-User-Id stub (see lib/api.ts). */
  readonly VITE_USER_ID?: string
}

// plotly.js ships its per-trace modules as untyped CommonJS. We only need
// them as opaque values to hand to Plotly.register() / the react factory.
declare module 'plotly.js/lib/core' {
  const Plotly: { register: (modules: unknown[]) => void }
  export default Plotly
}
declare module 'plotly.js/lib/*' {
  const traceModule: unknown
  export default traceModule
}
