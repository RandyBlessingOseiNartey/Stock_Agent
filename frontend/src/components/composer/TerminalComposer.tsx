import { RESPONSE_STYLE_OPTIONS } from '../../lib/labels'
import type { ResponseStyle } from '../../lib/types'
import { Composer } from './Composer'
import { Dropdown } from './Dropdown'

interface TerminalComposerProps {
  value: string
  onChange: (value: string) => void
  responseStyle: ResponseStyle
  onResponseStyleChange: (value: ResponseStyle) => void
  onSubmit: () => void
  busy: boolean
}

/** No Risk Appetite here — Terminal agents don't take that parameter. */
export function TerminalComposer(props: TerminalComposerProps) {
  return (
    <Composer
      value={props.value}
      onChange={props.onChange}
      onSubmit={props.onSubmit}
      busy={props.busy}
      autoFocus
      placeholder="Enter a company name or ticker..."
      ariaLabel="Company to analyze"
      trailing={
        <Dropdown
          label="Style"
          value={props.responseStyle}
          options={RESPONSE_STYLE_OPTIONS}
          onChange={props.onResponseStyleChange}
          placement="down"
        />
      }
    />
  )
}
