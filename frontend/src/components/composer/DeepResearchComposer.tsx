import { RESPONSE_STYLE_OPTIONS, RISK_APPETITE_OPTIONS } from '../../lib/labels'
import type { ResponseStyle, RiskAppetite } from '../../lib/types'
import { Composer } from './Composer'
import { Dropdown } from './Dropdown'

interface DeepResearchComposerProps {
  value: string
  onChange: (value: string) => void
  riskAppetite: RiskAppetite
  onRiskAppetiteChange: (value: RiskAppetite) => void
  responseStyle: ResponseStyle
  onResponseStyleChange: (value: ResponseStyle) => void
  onSubmit: () => void
  busy: boolean
}

export function DeepResearchComposer(props: DeepResearchComposerProps) {
  return (
    <Composer
      value={props.value}
      onChange={props.onChange}
      onSubmit={props.onSubmit}
      busy={props.busy}
      placeholder="Enter a company name or ticker..."
      ariaLabel="Company to research"
      leading={
        <Dropdown
          label="Risk"
          value={props.riskAppetite}
          options={RISK_APPETITE_OPTIONS}
          onChange={props.onRiskAppetiteChange}
          placement="down"
        />
      }
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
