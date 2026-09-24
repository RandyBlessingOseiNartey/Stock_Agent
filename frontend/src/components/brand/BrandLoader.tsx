import LoaderSvg from './stockagent-loader.svg?react'

/**
 * The one brand-mark size, used identically in Chat, Terminal and Deep
 * Research — animated loader and static bolt alike. Change it here and it
 * changes everywhere; no call site should pass its own size.
 */
export const BRAND_MARK_SIZE = 36

interface BrandLoaderProps {
  /** Rendered width and height in pixels. */
  size?: number
  /** For layout positioning by the parent. */
  className?: string
}

/**
 * The one and only loading indicator in StockAgent.
 *
 * Renders stockagent-loader.svg inline (via SVGR) so its embedded CSS
 * @keyframes actually run — they would not through <img> or a CSS
 * background. The bolt is white: only place it on a dark surface
 * (--sa-black / --sa-charcoal), never directly on a light one.
 */
export function BrandLoader({ size = BRAND_MARK_SIZE, className }: BrandLoaderProps) {
  return (
    <LoaderSvg
      width={size}
      height={size}
      className={className ? `brand-loader ${className}` : 'brand-loader'}
      focusable="false"
    />
  )
}
