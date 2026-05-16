import React from 'react'
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts'

/**
 * Global Integrity Overview Gauge
 * Shows how many employees are "In-Zone" (Productive) vs "Anomalous" (Risk)
 */

const COLORS = {
  inZone: '#10b981',    // Green
  anomalous: '#f59e0b', // Yellow/Orange
  critical: '#ef4444',  // Red
}

const CustomizedCell = ({ x, y, innerRadius, outerRadius, startAngle, endAngle, fill, payload }) => {
  if (payload.value === 0) return null
  
  return (
    <g>
      <path
        d={`
          M ${x + Math.cos((startAngle * Math.PI) / 180) * innerRadius} ${y + Math.sin((startAngle * Math.PI) / 180) * innerRadius}
          L ${x + Math.cos((startAngle * Math.PI) / 180) * outerRadius} ${y + Math.sin((startAngle * Math.PI) / 180) * outerRadius}
          A ${outerRadius} ${outerRadius} 0 ${endAngle - startAngle > 180 ? 1 : 0} ${x + Math.cos((endAngle * Math.PI) / 180) * outerRadius} ${y + Math.sin((endAngle * Math.PI) / 180) * outerRadius}
          L ${x + Math.cos((endAngle * Math.PI) / 180) * innerRadius} ${y + Math.sin((endAngle * Math.PI) / 180) * innerRadius}
          Z
        `}
        fill={fill}
        stroke="none"
      />
    </g>
  )
}

export default function IntegrityGauge({ summary }) {
  if (!summary) {
    return (
      <div className="flex items-center justify-center h-32">
        <div className="animate-pulse text-text-muted">Loading integrity data...</div>
      </div>
    )
  }

  const data = [
    { name: 'In Zone', value: summary.in_zone || 0, color: COLORS.inZone },
    { name: 'Anomalous', value: summary.anomalous || 0, color: COLORS.anomalous },
    { name: 'Critical', value: summary.critical || 0, color: COLORS.critical },
  ]

  const total = data.reduce((acc, curr) => acc + curr.value, 0) || 1
  const inZonePercent = Math.round(((summary.in_zone || 0) / total) * 100)
  const anomalousPercent = Math.round(((summary.anomalous || 0) / total) * 100)
  const criticalPercent = Math.round(((summary.critical || 0) / total) * 100)

  const getStatus = () => {
    if (criticalPercent > 20) return 'critical'
    if (anomalousPercent > 30) return 'warning'
    return 'healthy'
  }

  const status = getStatus()
  const statusColor = {
    healthy: 'text-emerald-400',
    warning: 'text-amber-400',
    critical: 'text-red-400',
  }[status]

  return (
    <div className="bg-surface-high rounded-xl p-6 border border-outline-variant/20">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-on-surface">Global Integrity Overview</h3>
        <div className={`text-xs font-mono px-2 py-1 rounded-full bg-surface-low ${statusColor}`}>
          {status.toUpperCase()}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Pie Chart */}
        <div className="flex items-center justify-center">
          <div className="relative w-32 h-32">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data}
                  cx="50%"
                  cy="50%"
                  innerRadius={40}
                  outerRadius={60}
                  startAngle={90}
                  endAngle={-270}
                  dataKey="value"
                  stroke="none"
                >
                  {data.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={entry.color}
                      payload={entry}
                    />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <div className="text-2xl font-bold font-mono text-on-surface">{total}</div>
                <div className="text-xs text-text-muted">Users</div>
              </div>
            </div>
          </div>
        </div>

        {/* Stats */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: COLORS.inZone }} />
              <span className="text-xs text-on-surface-variant">In Zone</span>
            </div>
            <div className="text-right">
              <div className="text-sm font-bold font-mono text-on-surface">{summary.in_zone || 0}</div>
              <div className="text-xs text-text-muted">{inZonePercent}%</div>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: COLORS.anomalous }} />
              <span className="text-xs text-on-surface-variant">Anomalous</span>
            </div>
            <div className="text-right">
              <div className="text-sm font-bold font-mono text-on-surface">{summary.anomalous || 0}</div>
              <div className="text-xs text-text-muted">{anomalousPercent}%</div>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: COLORS.critical }} />
              <span className="text-xs text-on-surface-variant">Critical</span>
            </div>
            <div className="text-right">
              <div className="text-sm font-bold font-mono text-on-surface">{summary.critical || 0}</div>
              <div className="text-xs text-text-muted">{criticalPercent}%</div>
            </div>
          </div>
        </div>

        {/* Risk Metrics */}
        <div className="bg-surface-low rounded-lg p-4 space-y-2">
          <div>
            <div className="text-xs text-text-muted">Avg Risk Score</div>
            <div className="text-lg font-bold font-mono text-on-surface">
              {summary.avg_risk_score ? summary.avg_risk_score.toFixed(1) : '0.0'}
            </div>
          </div>
          <div>
            <div className="text-xs text-text-muted">Avg Productivity</div>
            <div className="text-lg font-bold font-mono text-on-surface">
              {summary.avg_productivity ? (summary.avg_productivity * 100).toFixed(0) + '%' : '0%'}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
