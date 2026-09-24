import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'

import { BrandLoader, BRAND_MARK_SIZE } from './BrandLoader'

/** Never show the loader for less than this — a sub-100ms flash reads as a glitch. */
const MIN_VISIBLE_MS = 250
/** Must match the .loader-stage__overlay opacity transition in styles/app.css. */
const FADE_MS = 220

type Phase = 'hidden' | 'visible' | 'fading'

interface LoaderStageProps {
  /** True from request dispatch until the stream's first event arrives. */
  pending: boolean
  size?: number
  /** Where the loader sits inside the reserved area. */
  align?: 'start' | 'center'
  /** Optional status copy shown beside the bolt (Deep Research). */
  label?: ReactNode
  /**
   * Minimum height of the stage. Always applied — not just while loading —
   * so the loader mounting/unmounting never shifts the layout.
   */
  reserve: number
  className?: string
  children?: ReactNode
}

/**
 * The shared request-lifecycle wrapper used identically by all three modes:
 *
 *   dispatch → loader visible (≥ MIN_VISIBLE_MS) → first event → loader
 *   fades out while the streamed content fades in.
 *
 * The loader is absolutely positioned over a reserved area, so it takes
 * no layout space of its own — zero layout shift on mount and unmount.
 * Error handling is the parent's job: when the stream fails the parent
 * flips `pending` to false and renders its error state as children.
 */
export function LoaderStage({ pending, size = BRAND_MARK_SIZE, align = 'center', label, reserve, className, children }: LoaderStageProps) {
  const [phase, setPhase] = useState<Phase>(pending ? 'visible' : 'hidden')
  const [contentReady, setContentReady] = useState(!pending)
  const shownAt = useRef(pending ? performance.now() : 0)

  useEffect(() => {
    if (pending) {
      shownAt.current = performance.now()
      setPhase('visible')
      setContentReady(false)
      return
    }
    if (phase === 'hidden') {
      setContentReady(true)
      return
    }
    const elapsed = performance.now() - shownAt.current
    const hold = window.setTimeout(() => {
      setPhase('fading')
      setContentReady(true)
    }, Math.max(0, MIN_VISIBLE_MS - elapsed))
    return () => window.clearTimeout(hold)
    // `phase` is intentionally not a dependency: this effect reacts to
    // `pending` flipping, and reads the phase current at that moment.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pending])

  useEffect(() => {
    if (phase !== 'fading') return
    const done = window.setTimeout(() => setPhase('hidden'), FADE_MS)
    return () => window.clearTimeout(done)
  }, [phase])

  const style = { minHeight: reserve } as CSSProperties

  return (
    <div className={`loader-stage ${className ?? ''}`} style={style}>
      {phase !== 'hidden' && (
        <div
          className={`loader-stage__overlay loader-stage__overlay--${align} ${phase === 'fading' ? 'is-fading' : ''}`}
          role="status"
          aria-live="polite"
        >
          <BrandLoader size={size} />
          {label && <span className="loader-stage__label">{label}</span>}
          <span className="visually-hidden">Loading</span>
        </div>
      )}
      <div className={`loader-stage__content ${contentReady ? 'is-ready' : ''}`}>{children}</div>
    </div>
  )
}
