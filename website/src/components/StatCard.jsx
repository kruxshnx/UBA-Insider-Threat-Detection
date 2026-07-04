import { Shield, Activity, AlertTriangle, Users, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { cn } from '../lib/utils'

/**
 * StatCard — a KPI tile: accent icon, label, big value, optional delta + subtitle.
 *
 * @param {'activity'|'alert'|'shield'|'users'|React.ComponentType} [icon='activity']
 * @param {string} label
 * @param {string|number} value
 * @param {'cyan'|'red'|'amber'|'green'|'blue'} [accent='cyan']
 * @param {number|string} [delta]   Numeric → renders arrow + sign; string → shown as-is.
 * @param {string} [subtitle]
 * @param {string} [className]
 *
 * @example <StatCard icon="alert" label="Open Alerts" value={12} accent="red" delta={-3} />
 */
const iconMap = { activity: Activity, alert: AlertTriangle, shield: Shield, users: Users }

const accentMap = {
  cyan:  { text: 'text-primary',  bg: 'bg-primary/10' },
  red:   { text: 'text-error',    bg: 'bg-error-container/25' },
  amber: { text: 'text-tertiary', bg: 'bg-tertiary-container/20' },
  green: { text: 'text-success',  bg: 'bg-success-dim/25' },
  blue:  { text: 'text-info',     bg: 'bg-info/10' },
}

export default function StatCard({
  icon = 'activity',
  label,
  value,
  accent = 'cyan',
  delta,
  subtitle,
  className = '',
}) {
  const Icon = typeof icon === 'function' ? icon : (iconMap[icon] || Activity)
  const a = accentMap[accent] || accentMap.cyan

  const numericDelta = typeof delta === 'number' ? delta : null
  const DeltaIcon = numericDelta == null ? null : numericDelta > 0 ? TrendingUp : numericDelta < 0 ? TrendingDown : Minus
  const deltaColor = numericDelta == null
    ? 'text-on-surface-muted'
    : numericDelta > 0 ? 'text-success' : numericDelta < 0 ? 'text-error' : 'text-on-surface-muted'

  return (
    <div className={cn('card card-hover p-5 flex items-start gap-4 animate-fade-in', className)}>
      <div className={cn('rounded-xl p-3 flex-shrink-0', a.bg)}>
        <Icon size={22} className={a.text} aria-hidden="true" />
      </div>
      <div className="min-w-0">
        <div className="text-2xl font-bold font-mono tracking-tight text-on-surface tabular-nums">
          {value ?? '—'}
        </div>
        <div className="text-sm text-on-surface-variant mt-0.5 truncate">{label}</div>
        {delta != null && (
          <div className={cn('flex items-center gap-1 mt-1 text-xs font-medium', deltaColor)}>
            {DeltaIcon && <DeltaIcon size={12} aria-hidden="true" />}
            <span>{numericDelta != null ? `${numericDelta > 0 ? '+' : ''}${delta}` : delta}</span>
          </div>
        )}
        {subtitle && <div className="text-xs text-on-surface-muted mt-1">{subtitle}</div>}
      </div>
    </div>
  )
}
