import { RESPONSE_STYLE_OPTIONS } from '../../lib/labels'
import type { ResponseStyle } from '../../lib/types'
import { Composer } from './Composer'
import { Dropdown } from './Dropdown'

interface ChatComposerProps {
  value: string
  onChange: (value: string) => void
  responseStyle: ResponseStyle
  onResponseStyleChange: (value: ResponseStyle) => void
  onSubmit: () => void
  busy: boolean
}

/** No Risk Appetite here — Chat has no such parameter. */
export function ChatComposer(props: ChatComposerProps) {
  return (
    <Composer
      value={props.value}
      onChange={props.onChange}
      onSubmit={props.onSubmit}
      busy={props.busy}
      autoFocus
      placeholder="Ask about any company, comparison, or strategy..."
      ariaLabel="Message StockAgent"
      trailing={
        <Dropdown
          label="Style"
          value={props.responseStyle}
          options={RESPONSE_STYLE_OPTIONS}
          onChange={props.onResponseStyleChange}
        />
      }
    />
  )
}
