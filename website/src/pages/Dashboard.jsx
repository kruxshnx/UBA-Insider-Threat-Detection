import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Activity, Users, AlertTriangle, TrendingUp, Clock, RefreshCw,
  ShieldAlert, BarChart2, Monitor, ExternalLink, Zap, Eye
} from 'lucide-react'
import { fetchUsers, fetchIntegritySummary, fetchStats, fetchRiskyUsers, fetchAlerts } from '../services/api'

const getRiskColor = (score) => {
  if (score >= 80) return 'text-red-500'
  if (score >= 60) return 'text-orange-400'
  if (score >= 40) return 'text-yellow-400'
  return 'text-green-400'
}

const getRiskBg = (score) => {
  if (score >= 80) return 'bg-red-500/10 border-red-500/20'
  if (score >= 60) return 'bg-orange-500/10 border-orange-500/20'
  if (score >= 40) return 'bg-yellow-500/10 border-yellow-500/20'
  return 'bg-green-500/10 border-green-500/20'
}

const getRiskDot = (score) => {
  if (score >= 80) return 'bg-red-500'
  if (score >= 60) return 'bg-orange-400'
  if (score >= 40) return 'bg-yellow-400'
  return 'bg-green-400'
}

const getRiskBarColor = (score) => {
  if (score >= 80) return 'bg-red-500'
  if (score >= 60) return 'bg-orange-400'
  if (score >= 40) return 'bg-yellow-400'
  return 'bg-green-400'
}

const getRiskBadge = (level) => {
  const l = (level || 'Low').toLowerCase()
  if (l === 'critical') return 'bg-red-500/20 text-red-400 border border-red-500/40'
  if (l === 'high')     return 'bg-orange-500/20 text-orange-400 border border-orange-500/40'
  if (l === 'medium')   return 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/40'
  return 'bg-green-500/20 text-green-400 border border-green-500/40'
}

const getSeverityBadge = (severity) => {
  const s = (severity || '').toLowerCase()
  if (s === 'critical') return 'bg-red-500/20 text-red-400 border border-red-500/30'
  if (s === 'high') return 'bg-orange-500/20 text-orange-400 border border-orange-500/30'
  return 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
}

const getSessionStatus = (lastSeen) => {
  if (!lastSeen) return { label: 'Offline', dot: 'bg-gray-500', text: 'text-gray-400' }
  const diffMs = Date.now() - new Date(lastSeen).getTime()
  const diffMin = diffMs / 60000
  if (diffMin < 2)  return { label: 'Active',   dot: 'bg-green-400 animate-pulse', text: 'text-green-400' }
  if (diffMin < 15) return { label: 'Idle',     dot: 'bg-yellow-400',              text: 'text-yellow-400' }
  return                    { label: 'Offline',  dot: 'bg-gray-500',                text: 'text-gray-400' }
}

const relativeTime = (lastSeen) => {
  if (!lastSeen) return '—'
  const diffMs = Date.now() - new Date(lastSeen).getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1)  return 'Just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffH = Math.floor(diffMin / 60)
  if (diffH < 24)   return `${diffH}h ago`
  return new Date(lastSeen).toLocaleDateString()
}

const cleanAppName = (app) => {
  if (!app || app === '—') return '—'
  return app.replace('.exe', '').replace(/^\./, '')
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [realtimeUsers, setRealtimeUsers] = useState([])
  const [integrity, setIntegrity] = useState(null)
  const [stats, setStats] = useState(null)
  const [topThreats, setTopThreats] = useState([])
  const [recentAlerts, setRecentAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState(new Date())

  const loadData = async () => {
    try {
      const [usersData, integrityData, statsData, threatsData, alertsData] = await Promise.all([
        fetchUsers(),
        fetchIntegritySummary(),
        fetchStats(),
        fetchRiskyUsers(5),
        fetchAlerts({ limit: 5 }),
      ])
      if (usersData && Array.isArray(usersData)) setRealtimeUsers(usersData)
      if (integrityData) setIntegrity(integrityData)
      if (statsData) setStats(statsData)
      if (threatsData && Array.isArray(threatsData)) setTopThreats(threatsData)
      if (alertsData?.alerts) setRecentAlerts(alertsData.alerts)
      setLastUpdate(new Date())
      setLoading(false)
    } catch (error) {
      console.error('Dashboard load error:', error)
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 5000)
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <Activity className="w-12 h-12 animate-spin text-primary mx-auto mb-4" />
          <p className="text-on-surface">Loading real-time data...</p>
        </div>
      </div>
    )
  }

  const totalUsers = stats?.total_users || realtimeUsers.length
  const highRiskUsers = stats?.high_risk_users ?? realtimeUsers.filter(u => (u.risk_score || 0) >= 50).length
  const totalEvents = stats?.total_events || 0
  const avgRisk = stats?.avg_risk_score?.toFixed(1) ?? (realtimeUsers.reduce((a, u) => a + (u.risk_score || 0), 0) / Math.max(realtimeUsers.length, 1)).toFixed(1)
  const activeCount = realtimeUsers.filter(u => getSessionStatus(u.last_seen).label === 'Active').length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-on-surface">Security Operations Dashboard</h1>
          <div className="flex items-center gap-2 mt-1 text-sm text-on-surface-muted">
            <Clock className="w-4 h-4" />
            <span>Last updated: {lastUpdate.toLocaleTimeString()}</span>
            <button onClick={loadData} className="ml-3 flex items-center gap-1 px-3 py-1 bg-primary/20 text-primary rounded hover:bg-primary/30 text-xs transition-colors">
              <RefreshCw className="w-3 h-3" /> Refresh
            </button>
          </div>
        </div>
        <div className="flex items-center gap-2 bg-green-500/10 border border-green-500/30 px-3 py-1.5 rounded-full">
          <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-xs text-green-400 font-mono font-medium">LIVE MONITORING</span>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-surface rounded-xl p-4 border border-surface-variant">
          <div className="flex items-center gap-2 mb-3">
            <Users className="w-4 h-4 text-primary" />
            <span className="text-xs text-on-surface-muted uppercase tracking-wide">Monitored Users</span>
          </div>
          <div className="text-3xl font-bold text-on-surface">{totalUsers}</div>
          <div className="text-xs text-on-surface-muted mt-1">
            <span className="text-green-400 font-medium">{activeCount} active</span> · {realtimeUsers.length} total
          </div>
        </div>
        <div className="bg-surface rounded-xl p-4 border border-surface-variant">
          <div className="flex items-center gap-2 mb-3">
            <ShieldAlert className="w-4 h-4 text-red-400" />
            <span className="text-xs text-on-surface-muted uppercase tracking-wide">High-Risk Users</span>
          </div>
          <div className="text-3xl font-bold text-red-400">{highRiskUsers}</div>
          <div className="text-xs text-on-surface-muted mt-1">risk score ≥ 50 / 100</div>
        </div>
        <div className="bg-surface rounded-xl p-4 border border-surface-variant">
          <div className="flex items-center gap-2 mb-3">
            <BarChart2 className="w-4 h-4 text-yellow-400" />
            <span className="text-xs text-on-surface-muted uppercase tracking-wide">Telemetry Events</span>
          </div>
          <div className="text-3xl font-bold text-on-surface">{totalEvents.toLocaleString()}</div>
          <div className="text-xs text-on-surface-muted mt-1">{stats?.high_risk_events?.toLocaleString() || 0} flagged anomalous</div>
        </div>
        <div className="bg-surface rounded-xl p-4 border border-surface-variant">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="w-4 h-4 text-orange-400" />
            <span className="text-xs text-on-surface-muted uppercase tracking-wide">Avg Risk Score</span>
          </div>
          <div className={`text-3xl font-bold ${getRiskColor(parseFloat(avgRisk))}`}>{avgRisk}</div>
          <div className="text-xs text-on-surface-muted mt-1">top threat: <span className="text-on-surface font-medium">{stats?.top_threat || '—'}</span></div>
        </div>
      </div>

      {/* Telemetry integrity row */}
      {integrity && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-surface rounded-xl p-4 border border-surface-variant col-span-2 lg:col-span-1">
            <p className="text-xs text-on-surface-muted mb-1">Users Tracked (Telemetry)</p>
            <p className="text-2xl font-bold text-on-surface">{integrity.total_users ?? 0}</p>
            <p className="text-xs text-on-surface-muted mt-1">avg risk {(integrity.avg_risk_score || 0).toFixed(1)}</p>
          </div>
          <div className="bg-green-500/5 rounded-xl p-4 border border-green-500/20">
            <p className="text-xs text-green-400 mb-1">In Zone (Normal)</p>
            <p className="text-2xl font-bold text-green-400">{integrity.in_zone ?? 0}</p>
          </div>
          <div className="bg-yellow-500/5 rounded-xl p-4 border border-yellow-500/20">
            <p className="text-xs text-yellow-400 mb-1">Anomalous Behaviour</p>
            <p className="text-2xl font-bold text-yellow-400">{integrity.anomalous ?? 0}</p>
          </div>
          <div className="bg-red-500/5 rounded-xl p-4 border border-red-500/20">
            <p className="text-xs text-red-400 mb-1">Critical Alerts</p>
            <p className="text-2xl font-bold text-red-400">{integrity.critical ?? 0}</p>
          </div>
        </div>
      )}

      {/* Top Threats + Recent Alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Threats */}
        <div className="bg-surface rounded-xl border border-surface-variant overflow-hidden">
          <div className="p-4 border-b border-surface-variant flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-red-400" />
              <h2 className="font-semibold text-on-surface text-sm">Top Threats</h2>
            </div>
            <span className="text-xs text-on-surface-muted">sorted by risk score</span>
          </div>
          <div className="divide-y divide-surface-variant/50">
            {topThreats.length === 0 ? (
              <p className="text-center text-xs text-on-surface-muted py-6">No threat data</p>
            ) : topThreats.map((u, i) => {
              const score = u.total_risk_score || 0
              return (
                <div key={u.user || i}
                  className="flex items-center gap-3 px-4 py-3 hover:bg-surface-variant/5 cursor-pointer"
                  onClick={() => navigate('/forensics')}>
                  <span className="text-xs font-mono text-on-surface-muted w-5 flex-shrink-0">#{i + 1}</span>
                  <div className={`w-2 h-2 rounded-full flex-shrink-0 ${getRiskDot(score)}`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-on-surface truncate">{u.name || u.user}</p>
                      <span className="text-xs font-mono text-on-surface-muted flex-shrink-0">{u.user}</span>
                    </div>
                    <p className="text-xs text-on-surface-muted">{u.role || 'Employee'} · {u.department || 'General'}</p>
                    <div className="mt-1.5 flex items-center gap-2">
                      <div className="flex-1 h-1.5 bg-surface-variant rounded-full overflow-hidden max-w-[100px]">
                        <div className={`h-full rounded-full ${getRiskBarColor(score)}`} style={{ width: `${Math.min(100, score)}%` }} />
                      </div>
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className={`text-lg font-bold font-mono ${getRiskColor(score)}`}>{score.toFixed(1)}</p>
                    <span className={`text-[0.6rem] font-bold px-1.5 py-0.5 rounded ${getRiskBadge(u.risk_level)}`}>{u.risk_level || 'Low'}</span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Recent Alerts */}
        <div className="bg-surface rounded-xl border border-surface-variant overflow-hidden">
          <div className="p-4 border-b border-surface-variant flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-orange-400" />
              <h2 className="font-semibold text-on-surface text-sm">Recent Alerts</h2>
            </div>
            <button onClick={() => navigate('/alerts')} className="text-xs text-primary hover:underline flex items-center gap-1">
              View all <ExternalLink className="w-3 h-3" />
            </button>
          </div>
          <div className="divide-y divide-surface-variant/50">
            {recentAlerts.length === 0 ? (
              <p className="text-center text-xs text-on-surface-muted py-6">No alerts yet</p>
            ) : recentAlerts.map((a, i) => (
              <div key={a.alert_id || i} className="px-4 py-3 hover:bg-surface-variant/5 cursor-pointer" onClick={() => navigate('/alerts')}>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-2.5 flex-1 min-w-0">
                    <span className={`mt-0.5 text-[0.6rem] font-bold px-1.5 py-0.5 rounded flex-shrink-0 ${getSeverityBadge(a.severity)}`}>{(a.severity || '').toUpperCase()}</span>
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        <p className="text-sm font-semibold text-on-surface">{a.name || a.user}</p>
                        <span className="text-xs font-mono text-on-surface-muted">({a.user})</span>
                      </div>
                      <p className="text-xs text-on-surface-muted truncate">{a.activity || 'Suspicious activity'}</p>
                      {a.active_app && a.active_app !== 'unknown' && (
                        <div className="flex items-center gap-1 mt-0.5">
                          <Monitor className="w-3 h-3 text-on-surface-muted" />
                          <span className="text-[0.65rem] text-on-surface-muted font-mono">{cleanAppName(a.active_app)}</span>
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <span className={`text-sm font-bold font-mono ${getRiskColor(a.risk_score || 0)}`}>{Math.round(a.risk_score || 0)}</span>
                    <p className="text-[0.65rem] text-on-surface-muted">{relativeTime(a.timestamp)}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Live Employee Sessions Table */}
      <div className="bg-surface rounded-xl border border-surface-variant overflow-hidden">
        <div className="p-4 border-b border-surface-variant flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-primary" />
            <h2 className="font-semibold text-on-surface text-sm">Live Employee Sessions</h2>
          </div>
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1 text-xs text-green-400"><span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />{activeCount} active</span>
            <span className="text-xs text-on-surface-muted font-mono">{realtimeUsers.length} total</span>
          </div>
        </div>
        {realtimeUsers.length === 0 ? (
          <div className="text-center py-10">
            <AlertTriangle className="w-8 h-8 mx-auto mb-3 text-on-surface-muted opacity-40" />
            <p className="text-sm text-on-surface-muted">No sessions — start the telemetry agent</p>
            <p className="text-xs text-on-surface-muted mt-1 font-mono">python -m src.telemetry.agent --user-id U001</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-surface-variant/10">
                <tr>
                  <th className="text-left py-3 px-4 text-xs font-semibold text-on-surface-muted uppercase tracking-wide">Employee</th>
                  <th className="text-left py-3 px-4 text-xs font-semibold text-on-surface-muted uppercase tracking-wide">Role · Dept</th>
                  <th className="text-left py-3 px-4 text-xs font-semibold text-on-surface-muted uppercase tracking-wide">Risk Score</th>
                  <th className="text-left py-3 px-4 text-xs font-semibold text-on-surface-muted uppercase tracking-wide">Productivity</th>
                  <th className="text-left py-3 px-4 text-xs font-semibold text-on-surface-muted uppercase tracking-wide">Active App</th>
                  <th className="text-left py-3 px-4 text-xs font-semibold text-on-surface-muted uppercase tracking-wide">Status · Last Seen</th>
                  <th className="text-left py-3 px-4 text-xs font-semibold text-on-surface-muted uppercase tracking-wide">Events</th>
                  <th className="py-3 px-4" />
                </tr>
              </thead>
              <tbody>
                {realtimeUsers.map((user) => {
                  const score = user.risk_score || 0
                  const prod = Math.min(100, (user.productivity_score || 0) * 100)
                  const status = getSessionStatus(user.last_seen)
                  const rowHighlight = score >= 80 ? 'bg-red-500/5 hover:bg-red-500/10' : score >= 60 ? 'bg-orange-500/5 hover:bg-orange-500/10' : 'hover:bg-surface-variant/5'
                  return (
                    <tr key={user.user_id} className={`border-t border-surface-variant/30 transition-colors cursor-pointer ${rowHighlight}`}
                      onClick={() => navigate('/forensics')}>
                      {/* Employee */}
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2.5">
                          <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 ${getRiskBg(score)} border`}>
                            {(user.name || 'U').charAt(0)}
                          </div>
                          <div>
                            <p className="text-sm font-semibold text-on-surface leading-tight">{user.name}</p>
                            <p className="text-[0.65rem] text-on-surface-muted font-mono">{user.user_id}</p>
                          </div>
                        </div>
                      </td>
                      {/* Role & Dept */}
                      <td className="py-3 px-4">
                        <p className="text-xs font-medium text-on-surface">{user.role}</p>
                        <p className="text-[0.65rem] text-on-surface-muted">{user.department}</p>
                      </td>
                      {/* Risk Score */}
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <div>
                            <div className="flex items-center gap-1.5 mb-1">
                              <span className={`text-base font-bold font-mono ${getRiskColor(score)}`}>{score.toFixed(1)}</span>
                              <span className={`text-[0.6rem] font-bold px-1.5 py-0.5 rounded ${getRiskBadge(user.risk_level)}`}>{user.risk_level || 'Low'}</span>
                            </div>
                            <div className="w-24 h-1.5 bg-surface-variant rounded-full overflow-hidden">
                              <div className={`h-full rounded-full transition-all ${getRiskBarColor(score)}`} style={{ width: `${score}%` }} />
                            </div>
                          </div>
                        </div>
                      </td>
                      {/* Productivity */}
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <div className="w-20 h-1.5 bg-surface-variant rounded-full overflow-hidden">
                            <div className="h-full bg-primary rounded-full transition-all" style={{ width: `${prod}%` }} />
                          </div>
                          <span className="text-xs font-medium text-on-surface">{prod.toFixed(0)}%</span>
                        </div>
                      </td>
                      {/* Active App */}
                      <td className="py-3 px-4">
                        {user.last_active_app && user.last_active_app !== '—' ? (
                          <div className="flex items-center gap-1.5">
                            <Monitor className="w-3 h-3 text-on-surface-muted flex-shrink-0" />
                            <span className="text-xs font-mono text-on-surface truncate max-w-[100px]" title={user.last_window_title}>
                              {cleanAppName(user.last_active_app)}
                            </span>
                          </div>
                        ) : (
                          <span className="text-xs text-on-surface-muted">—</span>
                        )}
                      </td>
                      {/* Status + Last Seen */}
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-1.5 mb-0.5">
                          <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${status.dot}`} />
                          <span className={`text-xs font-medium ${status.text}`}>{status.label}</span>
                        </div>
                        <p className="text-[0.65rem] text-on-surface-muted">{relativeTime(user.last_seen)}</p>
                      </td>
                      {/* Events */}
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-1">
                          <Zap className="w-3 h-3 text-on-surface-muted" />
                          <span className="text-xs font-mono text-on-surface">{(user.event_count || 0).toLocaleString()}</span>
                        </div>
                      </td>
                      {/* Action */}
                      <td className="py-3 px-4">
                        <button className="flex items-center gap-1 text-xs text-primary hover:text-primary/80 transition-colors"
                          onClick={e => { e.stopPropagation(); navigate('/forensics') }}>
                          <Eye className="w-3.5 h-3.5" /> Investigate
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
