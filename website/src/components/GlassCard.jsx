import { cn } from '../lib/utils'

/**
 * GlassCard — translucent glassmorphism panel.
 *
 * @param {boolean} [hover=true]  Enable the accent hover glow.
 * @param {string}  [as='div']    Element/component to render as.
 * @param {string}  [className]   Extra classes (padding, span, etc.).
 */
export default function GlassCard({ children, className = '', hover = true, as: Tag = 'div', ...props }) {
  return (
    <Tag
      className={cn('glass-card p-6', !hover && 'hover:border-[color-mix(in_srgb,#fff_7%,transparent)] hover:shadow-none', className)}
      {...props}
    >
      {children}
    </Tag>
  )
}
