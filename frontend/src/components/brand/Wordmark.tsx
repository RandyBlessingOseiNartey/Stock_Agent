interface BoltProps {
  size?: number
  className?: string
}

/** The double-parallelogram bolt. Takes its fill from CSS `color`. */
export function Bolt({ size = 24, className }: BoltProps) {
  return (
    <svg
      viewBox="9 8 38 68"
      height={size}
      width={(size * 38) / 68}
      className={className}
      fill="currentColor"
      aria-hidden="true"
    >
      <polygon points="47,8 21,8 9,42 21,42 9,76 35,76 47,42 35,42" shapeRendering="geometricPrecision" />
    </svg>
  )
}

interface WordmarkProps {
  /** Cap height of the lockup in pixels. */
  size?: number
  /** "accent" is the split-color splash treatment — use sparingly. */
  variant?: 'default' | 'accent'
  className?: string
}

/**
 * Full lockup: bolt + "StockAgent". Built from markup rather than the
 * lockup SVG files because an SVG loaded through <img> cannot load web
 * fonts — the wordmark would silently fall back off Space Grotesk.
 */
export function Wordmark({ size = 22, variant = 'default', className }: WordmarkProps) {
  return (
    <span className={`lockup ${className ?? ''}`} style={{ fontSize: size, gap: size * 0.36 }}>
      <Bolt size={size * 1.18} />
      <span className="wordmark">
        Stock{variant === 'accent' ? <span className="wordmark-accent">Agent</span> : 'Agent'}
      </span>
    </span>
  )
}
