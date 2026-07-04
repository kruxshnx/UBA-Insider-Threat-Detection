import React, { useState, useEffect } from 'react'
import {
  ScatterChart, Scatter, XAxis, YAxis, ZAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { fetchIntegritySummary, fetchUserTelemetry } from '../services/api'

/**
 * Behavioral Signature Widget
 * Displays:
 * - Keystroke Dynamics Scatter Plot
 * - Mouse Activity Heatmap
 * - Live Activity Feed
 */

// Custom Scatter Point for Keystroke Dynamics
const CustomScatterPoint = ({ cx, cy, payload, size }) => {
  const { risk_score } = payload
  
  let fill = '#10b981' // Green - low risk
  if (risk_score > 50) fill = '#f59e0b' // Yellow - medium risk
  if (risk_score > 80) fill = '#ef4444' // Red - high risk
  
  return (
    <g>
      <circle cx={cx} cy={cy} r={size} fill={fill} stroke="#fff" strokeWidth={1} />
      <text x={cx} y={cy} textAnchor="middle" dy={4} fontSize="8" fill="#fff">
        {payload.user_id}
      </text>
    </g>
  )
}

// Keystroke Dynamics Scatter Plot
export function KeystrokeScatter({ data = [] }) {
  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 bg-surface-high rounded-lg">
        <div className="text-text-muted text-sm">No keystroke data available</div>
      </div>
    )
  }

  return (
    <div className="bg-surface-high rounded-lg p-4 border border-outline-variant/20">
      <h4 className="text-sm font-semibold text-on-surface mb-3">Keystroke Dynamics</h4>
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis
              type="number"
              dataKey="flight_time"
              name="Flight Time (ms)"
              label={{ value: 'Avg Flight Time (ms)', position: 'insideBottom', offset: -5, fill: '#9CA3AF', fontSize: 10 }}
              stroke="#9CA3AF"
              fontSize={10}
            />
            <YAxis
              type="number"
              dataKey="productivity"
              name="Productivity"
              label={{ value: 'Productivity Score', angle: -90, position: 'insideLeft', fill: '#9CA3AF', fontSize: 10 }}
              stroke="#9CA3AF"
              fontSize={10}
              domain={[0, 100]}
            />
            <ZAxis type="number" dataKey="risk_score" range={[50, 400]} name="Risk Score" />
            <Tooltip
              cursor={{ strokeDasharray: '3 3' }}
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const data = payload[0].payload
                  return (
                    <div className="bg-surface-lowest border border-outline-variant p-2 rounded text-xs">
                      <div className="font-bold text-on-surface">{data.user_id}</div>
                      <div className="text-text-muted">Flight: {data.flight_time.toFixed(1)}ms</div>
                      <div className="text-text-muted">Productivity: {data.productivity.toFixed(0)}%</div>
                      <div className="text-text-muted">Risk: {data.risk_score.toFixed(1)}</div>
                    </div>
                  )
                }
                return null
              }}
            />
            <Scatter
              name="Users"
              data={data}
              fill="#3B82F6"
              shape={<CustomScatterPoint />}
            />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

// Mouse Activity Heatmap Component
export function MouseActivityHeatmap({ data = [] }) {
  const hours = Array.from({ length: 24 }, (_, i) => i)
  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

  const getHeatColor = (intensity) => {
    if (intensity === 0) return 'bg-surface-highest'
    if (intensity < 30) return 'bg-emerald-500/30'
    if (intensity < 60) return 'bg-emerald-500/60'
    if (intensity < 80) return 'bg-amber-500/60'
    return 'bg-red-500/80'
  }

  return (
    <div className="bg-surface-high rounded-lg p-4 border border-outline-variant/20">
      <h4 className="text-sm font-semibold text-on-surface mb-3">Mouse Activity Heatmap</h4>
      <div className="overflow-x-auto">
        <div className="min-w-[400px]">
          {/* Hour labels */}
          <div className="flex mb-2 ml-12">
            {hours.filter((_, i) => i % 2 === 0).map(hour => (
              <div key={hour} className="flex-1 text-center text-xs text-text-muted">
                {hour}:00
              </div>
            ))}
          </div>
          
          {/* Heatmap grid */}
          <div className="space-y-1">
            {days.map((day, dayIdx) => (
              <div key={day} className="flex items-center gap-1">
                <div className="w-10 text-xs text-text-muted">{day}</div>
                {hours.map(hour => {
                  // Simulate data lookup
                  const intensity = data[dayIdx]?.[hour] || 0
                  return (
                    <div
                      key={hour}
                      className={`flex-1 h-4 rounded ${getHeatColor(intensity)}`}
                      title={`${day} ${hour}:00 - Intensity: ${intensity}`}
                    />
                  )
                })}
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="flex items-center justify-center gap-4 mt-4 text-xs text-text-muted">
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-surface-highest" />
          <span>Inactive</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-emerald-500/60" />
          <span>Normal</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-amber-500/60" />
          <span>Elevated</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-red-500/80" />
          <span>Anomalous</span>
        </div>
      </div>
    </div>
  )
}

// Live Activity Feed
export function LiveActivityFeed({ activities = [] }) {
  return (
    <div className="bg-surface-high rounded-lg p-4 border border-outline-variant/20">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold text-on-surface">Live Activity Feed</h4>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-xs text-text-muted">Live</span>
        </div>
      </div>
      
      <div className="space-y-2 max-h-64 overflow-y-auto">
        {activities.length === 0 ? (
          <div className="text-center text-text-muted text-sm py-8">
            No recent activity
          </div>
        ) : (
          activities.slice(0, 20).map((activity, idx) => (
            <div
              key={idx}
              className={`flex items-center justify-between p-2 rounded text-xs border-l-2 ${
                activity.risk_score > 80
                  ? 'bg-red-500/10 border-red-500'
                  : activity.risk_score > 50
                  ? 'bg-amber-500/10 border-amber-500'
                  : 'bg-emerald-500/10 border-emerald-500'
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="text-text-muted font-mono">{activity.time}</span>
                <span className="text-on-surface font-medium">{activity.user}</span>
                <span className="text-on-surface-variant">→</span>
                <span className="text-on-surface">{activity.app}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-text-muted">{activity.category}</span>
                <span className={`font-mono px-2 py-0.5 rounded ${
                  activity.risk_score > 80
                    ? 'bg-red-500/20 text-red-400'
                    : activity.risk_score > 50
                    ? 'bg-amber-500/20 text-amber-400'
                    : 'bg-emerald-500/20 text-emerald-400'
                }`}>
                  {activity.integrity_score}
                </span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

// Main Behavioral Signature Widget
export default function BehavioralSignatureWidget({ userId }) {
  const [keystrokeData, setKeystrokeData] = useState([])
  const [heatmapData, setHeatmapData] = useState([])
  const [activities, setActivities] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true)
        
        // Fetch recent telemetry
        const telemetry = await fetchUserTelemetry(userId, 100)
        
        // Process keystroke data
        if (telemetry?.telemetry) {
          const scatter = telemetry.telemetry.map(t => ({
            user_id: t.user_id,
            flight_time: t.keystroke_flight_avg_ms || 0,
            productivity: (t.productivity_score || 0) * 100,
            risk_score: t.risk_score || 0,
          }))
          setKeystrokeData(scatter)
          
          // Process activity feed
          const feed = telemetry.telemetry.slice(0, 20).map(t => ({
            time: new Date(t.timestamp).toLocaleTimeString(),
            user: t.user_id,
            app: t.active_app,
            category: t.productivity_score > 0.7 ? 'Productive' : 'Neutral',
            integrity_score: Math.round((t.productivity_score || 0) * 100),
            risk_score: t.risk_score || 0,
          }))
          setActivities(feed)
        }
      } catch (error) {
        console.error('Error loading behavioral data:', error)
      } finally {
        setLoading(false)
      }
    }

    if (userId) {
      loadData()
      
      // Refresh every 30 seconds
      const interval = setInterval(loadData, 30000)
      return () => clearInterval(interval)
    }
  }, [userId])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-text-muted">Loading behavioral data...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <KeystrokeScatter data={keystrokeData} />
      <MouseActivityHeatmap data={heatmapData} />
      <LiveActivityFeed activities={activities} />
    </div>
  )
}
