import { cn } from '../../lib/utils'

/**
 * SectionHeader — a titled row for the top of a card/panel, with an optional
 * icon, subtitle/description, and a right-aligned actions slot.
 *
 * @param {React.ComponentType} [icon]   lucide icon component.
 * @param {string} title
 * @param {string} [subtitle]            small meta line under the title.
 * @param {React.ReactNode} [actions]    right-side controls (buttons, links).
 * @param {boolean} [divider=false]      draw a bottom border (for padded headers).
 * @param {string} [iconColor='text-primary']
 *
 * @example <SectionHeader icon={ShieldAlert} title="Top Threats" subtitle="by risk" actions={<a>View all</a>} />
 */
export function SectionHeader({
  icon: Icon,
  title,
  subtitle,
  actions,
  divider = false,
  iconColor = 'text-primary',
  className = '',
}) {
  return (
    <div
      className={cn(
        'flex items-center justify-between gap-3',
        divider && 'pb-3 mb-4 border-b border-surface-variant',
        className,
      )}
    >
      <div className="flex items-center gap-2.5 min-w-0">
        {Icon && (
          <div className="flex-shrink-0">
            <Icon size={16} className={iconColor} aria-hidden="true" />
          </div>
        )}
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-on-surface truncate">{title}</h3>
          {subtitle && <p className="text-xs text-on-surface-muted truncate">{subtitle}</p>}
        </div>
      </div>
      {actions && <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>}
    </div>
  )
}

export default SectionHeader
