import { cn } from '../../lib/utils'

/**
 * Card — the default solid tonal panel.
 * @param {boolean} [hover=false]  Enable accent hover glow.
 * @param {boolean} [glass=false]  Use the translucent glass surface instead.
 * @param {string}  [padding='p-5']  Padding utility (pass '' or 'p-0' to opt out).
 * @param {string}  [as='div']
 *
 * @example <Card hover className="lg:col-span-2">…</Card>
 */
export function Card({ children, className = '', hover = false, glass = false, padding = 'p-5', as: Tag = 'div', ...props }) {
  return (
    <Tag
      className={cn(glass ? 'glass-card' : 'card', hover && !glass && 'card-hover', padding, className)}
      {...props}
    >
      {children}
    </Tag>
  )
}

/**
 * Panel — a larger section container (14px radius), typically holding a
 * SectionHeader + body. Use `padding=''` when it wraps a full-bleed table.
 *
 * @example <Panel padding="p-0"><SectionHeader …/><div className="table-scroll">…</div></Panel>
 */
export function Panel({ children, className = '', padding = 'p-5', as: Tag = 'div', ...props }) {
  return (
    <Tag className={cn('panel overflow-hidden', padding, className)} {...props}>
      {children}
    </Tag>
  )
}

export default Card
