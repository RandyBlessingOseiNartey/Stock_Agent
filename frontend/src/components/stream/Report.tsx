import { memo } from 'react'
import Markdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'

// Financial reports lean on wide GFM tables — give each one its own
// horizontal scroller so the page itself never scrolls sideways.
const components: Components = {
  table: ({ node: _node, ...props }) => (
    <div className="report__table-wrap">
      <table {...props} />
    </div>
  ),
  a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noreferrer noopener" />,
}

/** Markdown-rendered agent output (reports and chat replies). */
export const Report = memo(function Report({ text }: { text: string }) {
  return (
    <div className="report">
      <Markdown remarkPlugins={[remarkGfm]} components={components}>
        {text}
      </Markdown>
    </div>
  )
})
