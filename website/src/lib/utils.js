import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/** Merge conditional class names, de-duplicating Tailwind conflicts. */
export function cn(...inputs) {
  return twMerge(clsx(inputs))
}

/**
 * Shared chart palette (resolved hex, matched to the @theme tokens in index.css).
 * Use these for recharts fills/strokes so charts stay on-brand.
 */
export const CHART = {
  primary: '#4cd7f6',
  primaryContainer: '#06b6d4',
  grid: '#232936',        // --color-surface-variant
  axis: '#79839a',        // --color-on-surface-muted
  text: '#e4e9f5',        // --color-on-surface
  risk: {
    low: '#52e0a0',
    medium: '#fbbf24',
    high: '#f59e0b',
    critical: '#ff5a52',
  },
}

/** Map a 0–100 risk score to a band. */
export function riskBand(score) {
  const s = Number(score) || 0
  if (s >= 80) return 'critical'
  if (s >= 60) return 'high'
  if (s >= 40) return 'medium'
  return 'low'
}

/** Map a 0–100 risk score to its band hex colour. */
export function riskColor(score) {
  return CHART.risk[riskBand(score)]
}

/** Format a 0–1 ratio as a percentage string, e.g. 0.732 → "73%". */
export function formatPercent(ratio, digits = 0) {
  return `${(Number(ratio) * 100).toFixed(digits)}%`
}
