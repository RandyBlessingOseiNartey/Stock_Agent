import { useEffect, useRef, useState, type ReactNode } from 'react'

import { BrandLoader, BRAND_MARK_SIZE } from './BrandLoader'
import { Bolt } from './Wordmark'

/** Never animate for less than this — a sub-100ms flash reads as a glitch. */
const MIN_WORKING_MS = 300

interface WorkingMarkProps {
  /**
   * True for the whole time the agent is working — from dispatch through
   * tool events and token streaming, until the run's terminal event.
   */
  working: boolean
  /** What's happening right now, shown beside the mark while working. */
  status?: ReactNode
  /** Height of the bolt in pixels. Defaults to the one shared mark size. */
  size?: number
  className?: string
}

/**
 * The brand mark that lives in one fixed spot for a whole run: the animated
 * bolt while the agent works, settling into the static bolt when it's done —
 * the same mark, in the same place, so nothing jumps and there's never a
 * second indicator somewhere else on screen.
 *
 * Both states are stacked in a fixed-size slot and cross-faded, so the
 * swap costs zero layout shift.
 */
export function WorkingMark({ working, status, size = BRAND_MARK_SIZE, className }: WorkingMarkProps) {
  const [animating, setAnimating] = useState(working)
  const startedAt = useRef(working ? performance.now() : 0)

  useEffect(() => {
    if (working) {
      startedAt.current = performance.now()
      setAnimating(true)
      return
    }
    const elapsed = performance.now() - startedAt.current
    const hold = window.setTimeout(() => setAnimating(false), Math.max(0, MIN_WORKING_MS - elapsed))
    return () => window.clearTimeout(hold)
    // Reacts to `working` flipping; `animating` is read, not depended on.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [working])

  return (
    <div
      className={`working-mark ${className ?? ''}`}
      data-working={animating}
      role="status"
      aria-live="polite"
      aria-busy={animating}
    >
      {/* The slot is only as wide as the bolt itself (the loader's square
          canvas is mostly transparent padding), so the status text sits
          beside the mark rather than beside empty space. */}
      <span className="working-mark__slot" style={{ width: Math.round(size * 0.56), height: size }}>
        <BrandLoader size={size} className="working-mark__loader" />
        <Bolt size={size} className="working-mark__bolt" />
      </span>
      {animating && status && <span className="working-mark__status">{status}</span>}
      {animating && <span className="visually-hidden">Working</span>}
    </div>
  )
}
