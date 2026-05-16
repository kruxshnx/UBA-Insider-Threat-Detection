import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, ScatterChart, Scatter, ZAxis } from 'recharts'
import { RefreshCw, Search, Clock, ShieldAlert, Tag, Send, CheckCircle2, MousePointer2, Keyboard, Activity, TrendingUp, Monitor, Mail } from 'lucide-react'
import GlassCard from '../components/GlassCard'
import RiskBadge from '../components/RiskBadge'
import { GlowCard } from '../components/ui/spotlight-card'
import { fetchUserProfile, fetchTimeline, submitAnalystFeedback, fetchUserHourlyActivity, fetchUsers } from '../services/api'

const MITRE_TAGS = [
  { tactic: 'TA0010', name: 'Exfiltration',        technique: 'T1052 Physical Medium' },
  { tactic: 'TA0006', name: 'Credential Access',   technique: 'T1078 Valid Accounts' },
  { tactic: 'TA0009', name: 'Collection',           technique: 'T1560 Archive Data' },
  { tactic: 'TA0040', name: 'Impact',               technique: 'T1485 Data Destruction' },
]

const getRiskLevel = (score) => {
  if (score >= 80) return 'critical'
  if (score >= 60) return 'high'
  if (score >= 40) return 'medium'
  return 'low'
}

const riskColor = (score) => {
  if (score >= 80) return 'border-l-red-500'
  if (score >= 60) return 'border-l-orange-400'
  if (score >= 40) return 'border-l-yellow-400'
  return 'border-l-green-500'
}

// Keystroke Dynamics Component
function KeystrokeDynamics({ data = [] }) {
  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 bg-surface-high rounded-lg border border-outline-variant/20">
        <div className="text-text-muted text-sm">No keystroke data available</div>
      </div>
    )
  }

  return (
    <GlowCard customSize glowColor="blue" className="p-6">
      <div className="flex items-center gap-3 mb-4">
        <div className="p-2 rounded-lg bg-blue-500/10">
          <Keyboard size={18} className="text-blue-400" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-on-surface">Keystroke Dynamics</h3>
          <p className="text-xs text-text-muted">Flight time vs productivity analysis</p>
        </div>
      </div>
      <div className="h-64">
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
                  const d = payload[0].payload
                  return (
                    <div className="bg-surface-lowest border border-outline-variant p-2 rounded text-xs">
                      <div className="font-bold text-on-surface">{d.user}</div>
                      <div className="text-text-muted">Flight: {d.flight_time.toFixed(1)}ms</div>
                      <div className="text-text-muted">Productivity: {d.productivity.toFixed(0)}%</div>
                      <div className="text-text-muted">Risk: {d.risk_score.toFixed(1)}</div>
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
              shape={({ cx, cy, payload }) => {
                const color = payload.risk_score > 80 ? '#ef4444' : payload.risk_score > 50 ? '#f59e0b' : '#10b981'
                return <circle cx={cx} cy={cy} r={6} fill={color} stroke="#fff" strokeWidth={1} />
              }}
            />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </GlowCard>
  )
}

// Mouse Activity Heatmap — real telemetry data
function MouseActivityHeatmap({ hourlyData = [] }) {
  const hours = Array.from({ length: 24 }, (_, i) => i)
  const DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

  // Build 7x24 grid from real data
  const grid = Array.from({ length: 7 }, () => Array(24).fill(null))
  let maxRisk = 0
  for (const d of hourlyData) {
    const dow = d.day_of_week
    const h = d.hour
    if (dow >= 0 && dow < 7 && h >= 0 && h < 24) {
      grid[dow][h] = d
      if (d.avg_risk > maxRisk) maxRisk = d.avg_risk
    }
  }

  const getCellColor = (cell) => {
    if (!cell || cell.event_count === 0) return 'bg-surface-highest'
    const r = cell.avg_risk
    if (r >= 80) return 'bg-red-500/80'
    if (r >= 60) return 'bg-orange-400/70'
    if (r >= 40) return 'bg-amber-400/60'
    return 'bg-emerald-500/50'
  }

  const hasData = hourlyData.length > 0

  return (
    <GlowCard customSize glowColor="purple" className="p-6">
      <div className="flex items-center gap-3 mb-4">
        <div className="p-2 rounded-lg bg-purple-500/10">
          <MousePointer2 size={18} className="text-purple-400" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-on-surface">Activity Heatmap</h3>
          <p className="text-xs text-text-muted">{hasData ? 'Real telemetry · 7-day window' : 'No recent telemetry data'}</p>
        </div>
      </div>
      {!hasData ? (
        <div className="text-center py-8 text-text-muted text-xs">
          No telemetry recorded for this user in the last 7 days
        </div>
      ) : (
        <div className="overflow-x-auto">
          <div className="min-w-[380px]">
            <div className="flex mb-1 ml-10">
              {hours.filter((_, i) => i % 4 === 0).map(h => (
                <div key={h} className="flex-1 text-center text-[0.6rem] text-text-muted font-mono">{String(h).padStart(2,'0')}</div>
              ))}
            </div>
            <div className="space-y-0.5">
              {DAY_NAMES.map((day, di) => (
                <div key={day} className="flex items-center gap-0.5">
                  <div className="w-9 text-[0.65rem] text-text-muted flex-shrink-0">{day}</div>
                  {hours.map(h => {
                    const cell = grid[di][h]
                    return (
                      <div
                        key={h}
                        className={`flex-1 h-4 rounded-sm ${getCellColor(cell)}`}
                        title={cell ? `${day} ${String(h).padStart(2,'0')}:00 — Risk: ${cell.avg_risk.toFixed(1)}, Events: ${cell.event_count}` : 'No data'}
                      />
                    )
                  })}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
      <div className="flex items-center justify-center gap-4 mt-4 text-[0.65rem] text-text-muted">
        {[['bg-surface-highest','No data'],['bg-emerald-500/50','Low'],['bg-amber-400/60','Medium'],['bg-orange-400/70','High'],['bg-red-500/80','Critical']].map(([cls, lbl]) => (
          <div key={lbl} className="flex items-center gap-1">
            <div className={`w-3 h-3 rounded ${cls}`} />
            <span>{lbl}</span>
          </div>
        ))}
      </div>
    </GlowCard>
  )
}

// Live Activity Feed — real telemetry events
function LiveActivityFeed({ events = [] }) {
  const relTime = (ts) => {
    if (!ts) return '—'
    const diff = Math.floor((Date.now() - new Date(ts).getTime()) / 60000)
    if (diff < 1)  return 'Just now'
    if (diff < 60) return `${diff}m ago`
    return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <GlowCard customSize glowColor="green" className="p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-green-500/10">
            <Activity size={18} className="text-green-400" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-on-surface">Activity Timeline</h3>
            <p className="text-xs text-text-muted">{events.length} telemetry events loaded</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-xs text-text-muted font-mono">LIVE</span>
        </div>
      </div>

      <div className="space-y-1.5 max-h-80 overflow-y-auto pr-1">
        {events.length === 0 ? (
          <div className="text-center text-text-muted text-xs py-8">No telemetry events for this user</div>
        ) : (
          events.slice(0, 25).map((evt, idx) => {
            const score = evt.risk_score || 0
            const borderColor = score >= 80 ? 'border-red-500' : score >= 60 ? 'border-orange-400' : score >= 40 ? 'border-yellow-400' : 'border-green-500'
            const bg = score >= 80 ? 'bg-red-500/10' : score >= 60 ? 'bg-orange-400/10' : score >= 40 ? 'bg-yellow-400/10' : 'bg-emerald-500/10'
            return (
              <div key={idx} className={`flex items-center justify-between px-3 py-2 rounded-lg text-xs border-l-2 ${bg} ${borderColor}`}>
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-text-muted font-mono flex-shrink-0 text-[0.65rem]">{relTime(evt.timestamp)}</span>
                  <Monitor size={11} className="text-on-surface-variant flex-shrink-0" />
                  <span className="text-on-surface truncate max-w-[140px]">{evt.activity || 'Unknown'}</span>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0 ml-2">
                  {evt.is_anomaly && <span className="text-[0.6rem] bg-red-500/20 text-red-400 px-1.5 py-0.5 rounded font-mono">ANOMALY</span>}
                  <span className={`font-mono font-bold text-xs ${score >= 80 ? 'text-red-400' : score >= 60 ? 'text-orange-400' : score >= 40 ? 'text-yellow-400' : 'text-green-400'}`}>
                    {score.toFixed(1)}
                  </span>
                </div>
              </div>
            )
          })
        )}
      </div>
    </GlowCard>
  )
}

// Main Forensics Component
export default function Forensics() {
  const [searchParams] = useSearchParams()
  const [allUsers, setAllUsers] = useState([])
  const [selectedUser, setSelectedUser] = useState(null)
  const [profile, setProfile] = useState(null)
  const [timeline, setTimeline] = useState([])
  const [hourlyData, setHourlyData] = useState([])
  const [loading, setLoading] = useState(true)
  const [userLoading, setUserLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [highRiskOnly, setHighRiskOnly] = useState(false)
  const [isFP, setIsFP] = useState(false)
  const [notes, setNotes] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [keystrokeData, setKeystrokeData] = useState([])

  useEffect(() => {
    const init = async () => {
      const data = await fetchUsers()
      const sorted = (data || []).sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0))
      setAllUsers(sorted)
      const paramUser = searchParams.get('user')
      const initialUser = paramUser && sorted.find(u => u.user_id === paramUser)
        ? paramUser
        : sorted.length ? sorted[0].user_id : null
      if (initialUser) await selectUser(initialUser)
      else setLoading(false)
    }
    init()
  }, [])

  const selectUser = async (userId) => {
    setSelectedUser(userId)
    setSubmitted(false)
    setUserLoading(true)
    setTimeline([])
    setHourlyData([])
    setKeystrokeData([])

    const [p, t, h] = await Promise.all([
      fetchUserProfile(userId),
      fetchTimeline(userId, 200),
      fetchUserHourlyActivity(userId),
    ])
    setProfile(p)
    const evts = t?.events || []
    setTimeline(evts)
    setHourlyData(h?.data || [])

    const scatter = evts
      .filter(e => e.details?.keystroke_flight_ms > 0)
      .slice(0, 20)
      .map(e => ({
        user: userId,
        flight_time: e.details.keystroke_flight_ms,
        productivity: Math.min(100, Math.round((e.details?.productivity || 0) * 100)),
        risk_score: e.risk_score || 0,
      }))
    setKeystrokeData(scatter)
    setLoading(false)
    setUserLoading(false)
  }

  const handleSubmitFeedback = async () => {
    if (!selectedUser) return
    await submitAnalystFeedback({ userId: selectedUser, day: new Date().toISOString().split('T')[0], isFalsePositive: isFP, comments: notes })
    setSubmitted(true)
  }

  const filteredUsers = allUsers.filter(u =>
    u.user_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (u.name || '').toLowerCase().includes(searchQuery.toLowerCase())
  )

  const filteredTimeline = highRiskOnly
    ? timeline.filter(e => (e.risk_score || 0) >= 50)
    : timeline

  // Build daily aggregated chart data from real timeline events
  const dailyChartData = (() => {
    if (!timeline.length) return []
    const byDay = {}
    for (const e of timeline) {
      if (!e.timestamp) continue
      const day = e.timestamp.split('T')[0]
      if (!byDay[day]) byDay[day] = { scores: [], count: 0 }
      byDay[day].scores.push(e.risk_score || 0)
      byDay[day].count++
    }
    return Object.entries(byDay)
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(-30)
      .map(([day, v]) => ({
        day: day.slice(5),
        score: parseFloat((v.scores.reduce((a, b) => a + b, 0) / v.scores.length).toFixed(1)),
        events: v.count,
      }))
  })()

  // Risk factor breakdown from real profile data
  const riskFactors = profile ? [
    { name: 'Role Weight',    value: profile.role === 'Admin' ? 85 : profile.role === 'Manager' ? 70 : profile.role === 'Contractor' ? 65 : 40 },
    { name: 'Anomaly Rate',   value: timeline.length > 0 ? Math.round((timeline.filter(e => e.is_anomaly).length / timeline.length) * 100) : 0 },
    { name: 'Peak Risk',      value: Math.round(profile.max_risk_score || 0) },
    { name: 'Avg Risk Score', value: Math.round(profile.avg_risk_score || 0) },
  ] : []

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <RefreshCw size={28} className="text-primary animate-spin" />
      </div>
    )
  }

  const anomalyCount = timeline.filter(e => e.is_anomaly).length

  // Session stats from hourly data
  const sessionStats = (() => {
    if (!hourlyData.length) return null
    const withData = hourlyData.filter(d => d.event_count > 0)
    if (!withData.length) return null
    const avgMouse = withData.reduce((s, d) => s + d.avg_mouse_velocity, 0) / withData.length
    const avgFlight = withData.reduce((s, d) => s + d.avg_keystroke_flight_ms, 0) / withData.length
    const totalSlots = withData.length
    const peakHour = withData.reduce((max, d) => d.avg_risk > max.avg_risk ? d : max, withData[0])
    return {
      avgMouse: avgMouse.toFixed(1),
      avgFlight: avgFlight.toFixed(0),
      totalSlots,
      peakHour: `${String(peakHour.hour).padStart(2,'0')}:00`,
      peakRisk: peakHour.avg_risk.toFixed(1),
    }
  })()

  const userObj = allUsers.find(u => u.user_id === selectedUser)

  return (
    <div className="space-y-6 animate-fade-in">
      {/* User Selector + Profile */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* User list */}
        <GlassCard className="lg:col-span-1 p-4">
          <p className="text-xs font-semibold text-on-surface mb-2">Employees ({allUsers.length})</p>
          <div className="relative mb-3">
            <Search size={13} className="absolute left-3 top-2.5 text-text-muted" />
            <input
              type="text" placeholder="Search name or ID..."
              value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
              className="w-full bg-surface-lowest text-on-surface text-xs font-mono pl-8 pr-3 py-2 rounded-lg border border-outline-variant/20 focus:outline-none focus:border-primary/40"
            />
          </div>
          <div className="space-y-0.5 max-h-64 overflow-y-auto">
            {filteredUsers.map(u => {
              const score = u.risk_score || 0
              const dotColor = score >= 80 ? 'bg-red-500' : score >= 60 ? 'bg-orange-400' : score >= 40 ? 'bg-yellow-400' : 'bg-green-400'
              return (
                <button
                  key={u.user_id}
                  onClick={() => selectUser(u.user_id)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-all ${
                    selectedUser === u.user_id
                      ? 'bg-primary/10 text-primary border border-primary/20'
                      : 'text-on-surface-variant hover:bg-surface-highest'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${dotColor}`} />
                    <span className="font-medium truncate">{u.name || u.user_id}</span>
                    <span className="ml-auto font-mono text-[0.6rem] opacity-70">{score.toFixed(0)}</span>
                  </div>
                  <span className="block text-[0.6rem] text-text-muted ml-3.5">{u.user_id} · {u.role}</span>
                </button>
              )
            })}
          </div>
        </GlassCard>

        {/* Profile card */}
        {userLoading ? (
          <GlassCard className="lg:col-span-3 p-5 flex items-center justify-center">
            <RefreshCw size={20} className="text-primary animate-spin mr-2" />
            <span className="text-sm text-text-muted">Loading profile…</span>
          </GlassCard>
        ) : profile ? (
          <GlassCard className="lg:col-span-3 p-5">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-lg font-bold border ${
                  (profile.total_risk_score || 0) >= 80 ? 'bg-red-500/10 border-red-500/30 text-red-400' :
                  (profile.total_risk_score || 0) >= 60 ? 'bg-orange-500/10 border-orange-500/30 text-orange-400' :
                  'bg-primary/10 border-primary/20 text-primary'
                }`}>
                  {(profile.name || selectedUser || 'U').charAt(0)}
                </div>
                <div>
                  <h3 className="text-lg font-bold text-on-surface">{profile.name || selectedUser}</h3>
                  <p className="text-xs text-text-muted font-mono">{selectedUser} · {profile.role} · {profile.department}</p>
                  {userObj?.email && (
                    <p className="text-xs text-text-muted mt-0.5 flex items-center gap-1">
                      <Mail size={10} /> {userObj.email}
                    </p>
                  )}
                  {profile.last_seen && (
                    <p className="text-xs text-text-muted mt-0.5 flex items-center gap-1">
                      <Clock size={10} /> Last seen: {new Date(profile.last_seen).toLocaleString()}
                    </p>
                  )}
                </div>
              </div>
              <div className="text-right">
                <div className={`text-3xl font-bold font-mono ${
                  (profile.total_risk_score || 0) >= 80 ? 'text-red-400' :
                  (profile.total_risk_score || 0) >= 60 ? 'text-orange-400' :
                  (profile.total_risk_score || 0) >= 40 ? 'text-yellow-400' : 'text-green-400'
                }`}>{(profile.total_risk_score || 0).toFixed(1)}</div>
                <p className="text-[0.65rem] text-text-muted">Risk Score / 100</p>
                <RiskBadge level={getRiskLevel(profile.total_risk_score || 0)} className="mt-1" />
                {profile.rank && <p className="text-[0.65rem] text-text-muted mt-1">Rank #{profile.rank} most risky</p>}
              </div>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="bg-surface-high rounded-lg p-3">
                <p className="text-[0.65rem] text-text-muted">Total Events</p>
                <p className="text-base font-bold font-mono text-on-surface">{(profile.event_count || timeline.length).toLocaleString()}</p>
              </div>
              <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3">
                <p className="text-[0.65rem] text-red-400">Anomalies</p>
                <p className="text-base font-bold font-mono text-red-400">{anomalyCount}</p>
              </div>
              <div className="bg-surface-high rounded-lg p-3">
                <p className="text-[0.65rem] text-text-muted">Avg Risk</p>
                <p className="text-base font-bold font-mono text-on-surface">{(profile.avg_risk_score || 0).toFixed(1)}</p>
              </div>
              <div className="bg-surface-high rounded-lg p-3">
                <p className="text-[0.65rem] text-text-muted">Peak Risk</p>
                <p className={`text-base font-bold font-mono ${(profile.max_risk_score || 0) >= 80 ? 'text-red-400' : 'text-on-surface'}`}>
                  {(profile.max_risk_score || 0).toFixed(1)}
                </p>
              </div>
            </div>
          </GlassCard>
        ) : (
          <GlassCard className="lg:col-span-3 p-5 flex items-center justify-center text-text-muted text-sm">
            Select an employee to view their forensic profile
          </GlassCard>
        )}
      </div>

      {/* Session Stats — from real hourly data */}
      {sessionStats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <GlassCard className="p-4">
            <p className="text-xs text-text-muted mb-1">Avg Mouse Velocity</p>
            <p className="text-xl font-bold font-mono text-on-surface">{sessionStats.avgMouse}</p>
            <p className="text-[0.65rem] text-text-muted">px/s avg over 7 days</p>
          </GlassCard>
          <GlassCard className="p-4">
            <p className="text-xs text-text-muted mb-1">Avg Keystroke Flight</p>
            <p className="text-xl font-bold font-mono text-on-surface">{sessionStats.avgFlight}<span className="text-xs font-normal">ms</span></p>
            <p className="text-[0.65rem] text-text-muted">inter-key latency avg</p>
          </GlassCard>
          <GlassCard className="p-4">
            <p className="text-xs text-text-muted mb-1">Active Hours (7d)</p>
            <p className="text-xl font-bold font-mono text-on-surface">{sessionStats.totalSlots}</p>
            <p className="text-[0.65rem] text-text-muted">day×hour slots with activity</p>
          </GlassCard>
          <GlassCard className="p-4">
            <p className="text-xs text-text-muted mb-1">Peak Risk Hour</p>
            <p className="text-xl font-bold font-mono text-on-surface">{sessionStats.peakHour}</p>
            <p className="text-[0.65rem] text-text-muted">avg {sessionStats.peakRisk} risk score</p>
          </GlassCard>
        </div>
      )}

      {/* Analysis + Behavioral Widgets */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-6">
          {/* Risk trend chart — real daily data */}
          <GlowCard customSize glowColor="blue" className="p-6">
            <h3 className="text-sm font-semibold text-on-surface mb-1">Risk Score Trend</h3>
            <p className="text-xs text-text-muted mb-4">
              {dailyChartData.length > 0 ? `${dailyChartData.length} days of real telemetry` : 'No timeline data'}
            </p>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={dailyChartData.length > 0 ? dailyChartData : [{day:'—', score:0}]}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#303541" />
                  <XAxis dataKey="day" stroke="#6b7280" fontSize={9} />
                  <YAxis stroke="#6b7280" fontSize={9} domain={[0, 100]} />
                  <Tooltip
                    contentStyle={{ background: '#1b1f2b', border: '1px solid #3d494c', borderRadius: 8, fontSize: 11 }}
                    formatter={(val, name) => [val, name === 'score' ? 'Avg Risk' : 'Events']}
                  />
                  <Line type="monotone" dataKey="score" stroke="#ef4444" strokeWidth={2} dot={false} name="score" />
                  <Line type="monotone" dataKey="events" stroke="#4cd7f6" strokeWidth={1} dot={false} name="events" strokeDasharray="4 2" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </GlowCard>

          {/* Risk Factor Breakdown — real values */}
          <GlowCard customSize glowColor="blue" className="p-6">
            <h3 className="text-sm font-semibold text-on-surface mb-4">Risk Factor Breakdown</h3>
            <div className="h-44">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={riskFactors} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#303541" />
                  <XAxis type="number" stroke="#6b7280" fontSize={9} domain={[0, 100]} />
                  <YAxis type="category" dataKey="name" stroke="#6b7280" fontSize={9} width={95} />
                  <Tooltip contentStyle={{ background: '#1b1f2b', border: '1px solid #3d494c', borderRadius: 8, fontSize: 11 }} />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]}
                    fill="#06b6d4"
                    label={{ position: 'right', fontSize: 9, fill: '#9ca3af', formatter: v => v > 0 ? v : '' }}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </GlowCard>

          {/* MITRE ATT&CK */}
          <GlassCard>
            <h3 className="text-sm font-semibold text-on-surface mb-3">MITRE ATT&CK Mapping</h3>
            <div className="flex flex-wrap gap-2">
              {MITRE_TAGS.map(t => (
                <div key={t.tactic} className="flex items-center gap-1.5 bg-surface-highest px-3 py-1.5 rounded-full">
                  <Tag size={10} className="text-tertiary" />
                  <span className="text-[0.65rem] font-mono text-tertiary">{t.tactic}</span>
                  <span className="text-[0.65rem] font-mono text-on-surface-variant">{t.name}</span>
                </div>
              ))}
            </div>
          </GlassCard>
        </div>

        <div className="space-y-6">
          {/* Keystroke Dynamics — real data */}
          <KeystrokeDynamics data={keystrokeData} />

          {/* Mouse/Activity Heatmap — real data */}
          <MouseActivityHeatmap hourlyData={hourlyData} />

          {/* Live Activity Feed — real timeline */}
          <LiveActivityFeed events={timeline} />
        </div>
      </div>

      {/* Full Event Timeline */}
      <GlassCard>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-on-surface">Full Event Timeline</h3>
            <p className="text-xs text-text-muted">{filteredTimeline.length} events{highRiskOnly ? ' (high-risk filtered)' : ''}</p>
          </div>
          <label className="flex items-center gap-2 text-xs text-text-muted cursor-pointer">
            <input type="checkbox" checked={highRiskOnly} onChange={e => setHighRiskOnly(e.target.checked)} className="accent-primary w-3.5 h-3.5" />
            High-risk only (≥50)
          </label>
        </div>
        <div className="space-y-1.5 max-h-[480px] overflow-y-auto pr-1">
          {filteredTimeline.length === 0 && (
            <p className="text-xs text-text-muted text-center py-8">No events — run the telemetry agent for this user.</p>
          )}
          {filteredTimeline.map((evt, i) => {
            const score = evt.risk_score || 0
            return (
              <div key={i} className={`bg-surface-high rounded-lg p-3 border-l-2 ${riskColor(score)}`}>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <Clock size={10} className="text-text-muted" />
                    <span className="text-[0.65rem] font-mono text-text-muted">
                      {evt.timestamp ? new Date(evt.timestamp).toLocaleString() : `Event #${i + 1}`}
                    </span>
                    {evt.is_anomaly && (
                      <span className="text-[0.6rem] bg-red-500/20 text-red-400 px-1.5 py-0.5 rounded font-mono">ANOMALY</span>
                    )}
                  </div>
                  <span className={`text-xs font-mono font-bold ${score >= 80 ? 'text-red-400' : score >= 60 ? 'text-orange-400' : score >= 40 ? 'text-yellow-400' : 'text-green-400'}`}>
                    {score.toFixed(1)}
                  </span>
                </div>
                <p className="text-xs text-on-surface-variant">{evt.activity || `Telemetry event #${i + 1}`}</p>
                {evt.details && (evt.details.keystroke_flight_ms > 0 || evt.details.mouse_velocity > 0) && (
                  <div className="flex gap-3 mt-1.5 text-[0.6rem] text-text-muted font-mono">
                    {evt.details.mouse_velocity > 0 && <span>🖱 {evt.details.mouse_velocity.toFixed(1)} vel</span>}
                    {evt.details.keystroke_flight_ms > 0 && <span>⌨ {evt.details.keystroke_flight_ms.toFixed(0)}ms flight</span>}
                    {evt.details.productivity > 0 && <span>📊 {(evt.details.productivity * 100).toFixed(0)}% prod</span>}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </GlassCard>

      {/* Analyst Notes */}
      <GlowCard customSize glowColor="purple" className="p-6">
        <h3 className="text-sm font-semibold text-on-surface mb-3">Analyst Notes</h3>
        <textarea
          value={notes} onChange={e => setNotes(e.target.value)}
          placeholder="Add investigation notes, findings, or escalation details..."
          className="w-full bg-surface-lowest text-on-surface text-xs font-mono p-3 rounded-lg border border-outline-variant/20 focus:outline-none focus:border-primary/40 resize-none h-24"
        />
        <div className="flex items-center justify-between mt-3">
          <label className="flex items-center gap-2 text-xs text-text-muted cursor-pointer">
            <input type="checkbox" checked={isFP} onChange={e => setIsFP(e.target.checked)} className="accent-tertiary w-3.5 h-3.5" />
            <ShieldAlert size={12} className="text-tertiary" />
            Mark as False Positive
          </label>
          <button
            onClick={handleSubmitFeedback}
            className="px-4 py-2 bg-primary hover:bg-primary/90 text-white rounded-lg text-xs font-medium transition-colors flex items-center gap-2"
          >
            {submitted ? <><CheckCircle2 size={14} /> Submitted</> : <><Send size={14} /> Submit Feedback</>}
          </button>
        </div>
      </GlowCard>
    </div>
  )
}
