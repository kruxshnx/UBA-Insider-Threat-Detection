const levelConfig = {
  critical: 'badge-critical',
  high: 'badge-high',
  medium: 'badge-medium',
  low: 'badge-low',
}

export default function RiskBadge({ level, className = '' }) {
  const levelClass = levelConfig[level] || levelConfig.low

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-mono font-medium uppercase tracking-wider ${levelClass} ${className}`}
    >
      {level}
    </span>
  )
}
