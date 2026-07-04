import { AlertOctagon, AlertTriangle, Info, CheckCircle2 } from 'lucide-react'
import { cn } from '../../lib/utils'

/**
 * SeverityPill — an alert/finding severity tag. Colour is always paired with a
 * label (and optional icon). Distinct from RiskBadge, which is for risk *bands*.
 *
 * @param {'critical'|'high'|'error'|'warning'|'medium'|'info'|'low'|'success'} severity
 * @param {boolean} [showIcon=true]
 * @param {string}  [label]   Override the displayed text.
 * @param {string}  [className]
 *
 * @example <SeverityPill severity="warning" />  <SeverityPill severity="info" label="New" />
 */
const config = {
  critical: { cls: 'badge-critical', Icon: AlertOctagon, label: 'Critical' },
  high:     { cls: 'badge-high',     Icon: AlertTriangle, label: 'High' },
  error:    { cls: 'badge-critical', Icon: AlertOctagon, label: 'Error' },
  warning:  { cls: 'badge-high',     Icon: AlertTriangle, label: 'Warning' },
  medium:   { cls: 'badge-medium',   Icon: AlertTriangle, label: 'Medium' },
  info:     { cls: 'badge-info',     Icon: Info,          label: 'Info' },
  low:      { cls: 'badge-low',      Icon: CheckCircle2,  label: 'Low' },
  success:  { cls: 'badge-low',      Icon: CheckCircle2,  label: 'Resolved' },
}

export function SeverityPill({ severity, showIcon = true, label, className = '' }) {
  const key = String(severity || 'info').toLowerCase()
  const c = config[key] || config.info
  const text = label ?? c.label
  return (
    <span className={cn('badge', c.cls, className)} role="status" aria-label={`Severity: ${text}`}>
      {showIcon && <c.Icon size={12} aria-hidden="true" />}
      {text}
    </span>
  )
}

export default SeverityPill
