import { cn } from '../../lib/utils'
import { riskColor } from '../../lib/utils'

/**
 * ProgressBar — a generic value/max track fill.
 * @param {number} value
 * @param {number} [max=100]
 * @param {string} [color]      CSS colour for the fill (default primary).
 * @param {string} [className]  Extra classes for the outer track (e.g. height).
 *
 * @example <ProgressBar value={72} className="h-1.5 max-w-[120px]" />
 */
export function ProgressBar({ value, max = 100, color = 'var(--color-primary)', className = '', 'aria-label': ariaLabel }) {
  const pct = Math.max(0, Math.min(100, (Number(value) / max) * 100))
  return (
    <div
      className={cn('track', className)}
      role="progressbar"
      aria-valuenow={Math.round(Number(value) || 0)}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-label={ariaLabel}
    >
      <div className="track-fill" style={{ width: `${pct}%`, background: color }} />
    </div>
  )
}

/**
 * RiskBar — a ProgressBar whose fill colour is derived from a 0–100 risk score.
 * @param {number} score  0–100.
 * @example <RiskBar score={83} className="h-1.5 max-w-[100px]" />
 */
export function RiskBar({ score, className = '' }) {
  return (
    <ProgressBar
      value={score}
      color={riskColor(score)}
      className={className}
      aria-label={`Risk score ${Math.round(Number(score) || 0)} of 100`}
    />
  )
}

export default RiskBar
