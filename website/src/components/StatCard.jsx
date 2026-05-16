import { Shield, Activity, AlertTriangle, Users, TrendingUp } from 'lucide-react'
import { GlowCard } from './ui/spotlight-card'

const iconMap = {
  activity: Activity,
  alert: AlertTriangle,
  shield: Shield,
  users: Users,
}

const accentMap = {
  cyan: 'text-primary',
  red: 'text-error',
  amber: 'text-tertiary',
  green: 'text-success',
}

const bgMap = {
  cyan: 'bg-primary/10',
  red: 'bg-error-container/30',
  amber: 'bg-tertiary-container/20',
  green: 'bg-success-dim/30',
}

const glowMap = {
  cyan: 'blue',
  red: 'red',
  amber: 'orange',
  green: 'green',
}

export default function StatCard({ icon = 'activity', label, value, accent = 'cyan', trend, subtitle }) {
  const Icon = iconMap[icon] || Activity
  const glowColor = glowMap[accent] || 'blue'
  const colorClass = accentMap[accent] || accentMap.cyan
  const bgClass = bgMap[accent] || bgMap.cyan

  return (
    <GlowCard customSize glowColor={glowColor} className="p-5 flex items-start gap-4 animate-fade-in">
      <div className={`${bgClass} rounded-xl p-3 flex-shrink-0`}>
        <Icon size={22} className={colorClass} />
      </div>
      <div className="min-w-0">
        <div className="text-2xl font-bold font-mono tracking-tight text-on-surface">
          {value ?? '—'}
        </div>
        <div className="text-sm text-on-surface-variant mt-0.5">{label}</div>
        {trend && (
          <div className="flex items-center gap-1 mt-1 text-xs text-tertiary">
            <TrendingUp size={12} />
            <span>{trend}</span>
          </div>
        )}
        {subtitle && (
          <div className="text-xs text-text-muted mt-1">{subtitle}</div>
        )}
      </div>
    </GlowCard>
  )
}
