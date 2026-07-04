import { ShieldAlert, ShieldX, ShieldQuestion, ShieldCheck } from 'lucide-react'
import { cn } from '../lib/utils'

/**
 * RiskBadge — colour-coded risk-band pill. Colour is always paired with a
 * label (and optional icon) — never colour alone.
 *
 * @param {'critical'|'high'|'medium'|'low'} level  Risk band (case-insensitive).
 * @param {number}  [score]        Optional score appended (e.g. "HIGH · 72").
 * @param {boolean} [showIcon=false]  Prefix a band icon.
 * @param {string}  [className]
 *
 * @example <RiskBadge level="critical" score={91} showIcon />
 */
const config = {
  critical: { cls: 'badge-critical', Icon: ShieldX, label: 'Critical' },
  high:     { cls: 'badge-high',     Icon: ShieldAlert, label: 'High' },
  medium:   { cls: 'badge-medium',   Icon: ShieldQuestion, label: 'Medium' },
  low:      { cls: 'badge-low',      Icon: ShieldCheck, label: 'Low' },
}

export default function RiskBadge({ level, score, showIcon = false, className = '' }) {
  const key = String(level || 'low').toLowerCase()
  const { cls, Icon, label } = config[key] || config.low

  return (
    <span
      className={cn('badge', cls, className)}
      role="status"
      aria-label={`Risk level: ${label}${score != null ? `, score ${score}` : ''}`}
    >
      {showIcon && <Icon size={12} aria-hidden="true" />}
      {label}
      {score != null && <span className="opacity-70">· {score}</span>}
    </span>
  )
}
