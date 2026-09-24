import { useLayoutEffect, useRef, type FormEvent, type KeyboardEvent, type ReactNode } from 'react'

interface ComposerProps {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  placeholder: string
  /** Disables sending (e.g. while a response is streaming). Typing stays enabled. */
  busy?: boolean
  /** Controls on the left of the toolbar row (e.g. Risk Appetite). */
  leading?: ReactNode
  /** Controls just left of Send (e.g. Response Style). */
  trailing?: ReactNode
  autoFocus?: boolean
  ariaLabel: string
}

const MAX_TEXTAREA_PX = 200

/**
 * The shared composer frame: the text field and the toolbar (dropdowns +
 * Send) live in one bordered box, so selections are made in the same
 * input area the user types into. Enter sends; Shift+Enter adds a line.
 */
export function Composer({ value, onChange, onSubmit, placeholder, busy, leading, trailing, autoFocus, ariaLabel }: ComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const canSend = value.trim().length > 0 && !busy

  // Grow with content up to a cap, then scroll.
  useLayoutEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, MAX_TEXTAREA_PX)}px`
  }, [value])

  const submit = (e?: FormEvent) => {
    e?.preventDefault()
    if (canSend) onSubmit()
  }

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <form className="composer" onSubmit={submit}>
      <textarea
        ref={textareaRef}
        className="composer__input"
        rows={1}
        value={value}
        placeholder={placeholder}
        aria-label={ariaLabel}
        autoFocus={autoFocus}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
      />
      <div className="composer__toolbar">
        <div className="composer__leading">{leading}</div>
        <div className="composer__trailing">
          {trailing}
          <button type="submit" className="btn-primary composer__send" disabled={!canSend}>
            Send
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <path d="M3 8h9M8.5 4.5 12 8l-3.5 3.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>
      </div>
    </form>
  )
}
