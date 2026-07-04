import { useState, useEffect, useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Users, ShieldAlert, Activity, Gauge, Crosshair, RefreshCw, Clock,
  AlertTriangle, Eye, Monitor, ExternalLink, Radar, ServerCrash, WifiOff,
} from 'lucide-react'
import {
  Card, Panel, SectionHeader, StatCard, RiskBadge, SeverityPill,
  DataTable, RiskBar, EmptyState, LoadingState, Button,
} from '../components/ui'
import { riskBand, riskColor } from '../lib/utils'
import {
  fetchStats, fetchRiskyUsers, fetchAlerts, fetchUsers, fetchIntegritySummary,
} from '../services/api'

const POLL_MS = 5000

/* ── Small helpers (pure, defensive) ─────────────────────────────────────── */

const num = (v, d = 0) => (Number.isFinite(Number(v)) ? Number(v) : d)

const relativeTime = (ts) => {
  if (!ts) return '—'
  const t = new Date(ts).getTime()
  if (Number.isNaN(t)) return '—'
  const diffMin = Math.floor((Date.now() - t) / 60000)
  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffH = Math.floor(diffMin / 60)
  if (diffH < 24) return `${diffH}h ago`
  return new Date(ts).toLocaleDateString([], { month: 'short', day: 'numeric' })
}

const sessionState = (lastSeen) => {
  if (!lastSeen) return { key: 'offline', label: 'Offline', dot: 'bg-outline' }
  const t = new Date(lastSeen).getTime()
  if (Number.isNaN(t)) return { key: 'offline', label: 'Offline', dot: 'bg-outline' }
  const diffMin = (Date.now() - t) / 60000
  if (diffMin < 2) return { key: 'active', label: 'Active', dot: 'bg-success animate-pulse' }
  if (diffMin < 15) return { key: 'idle', label: 'Idle', dot: 'bg-tertiary' }
  return { key: 'offline', label: 'Offline', dot: 'bg-outline' }
}

const cleanApp = (app) => {
  if (!app || app === '—' || app === 'unknown') return null
  return app.replace(/\.exe$/i, '').replace(/^\./, '')
}

const initial = (s) => (s && typeof s === 'string' ? s.charAt(0).toUpperCase() : '?')

/* ── Page ─────────────────────────────────────────────────────────────────── */

export default function Dashboard() {
  const navigate = useNavigate()

  const [stats, setStats] = useState(null)
  const [topThreats, setTopThreats] = useState([])
  const [recentAlerts, setRecentAlerts] = useState([])
  const [sessions, setSessions] = useState([])
  const [integrity, setIntegrity] = useState(null)

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [lastUpdate, setLastUpdate] = useState(null)

  const loadData = useCallback(async () => {
    try {
      const [statsData, threatsData, alertsData, usersData, integrityData] = await Promise.all([
        fetchStats(),
        fetchRiskyUsers(6),
        fetchAlerts({ limit: 6 }),
        fetchUsers().catch(() => []),
        fetchIntegritySummary().catch(() => null),
      ])

      // Treat total loss of the primary pipeline as an error banner.
      const primaryDown = !statsData && (!Array.isArray(threatsData) || threatsData.length === 0)
      setError(primaryDown)

      if (statsData) setStats(statsData)
      setTopThreats(Array.isArray(threatsData) ? threatsData : [])
      setRecentAlerts(Array.isArray(alertsData?.alerts) ? alertsData.alerts : [])
      setSessions(Array.isArray(usersData) ? usersData : [])
      setIntegrity(integrityData || null)
      setLastUpdate(new Date())
    } catch (err) {
      console.error('Dashboard load error:', err)
      setError(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
    const iv = setInterval(loadData, POLL_MS)
    return () => clearInterval(iv)
  }, [loadData])

  /* ── Derived KPI values (honest fallbacks; never fabricated) ───────────── */

  const totalUsers = stats?.total_users ?? topThreats.length ?? 0
  const highRiskUsers = stats?.high_risk_users ?? topThreats.filter(u => num(u.total_risk_score) >= 50).length
  const totalEvents = num(stats?.total_events, 0)
  const highRiskEvents = num(stats?.high_risk_events, 0)
  const avgRisk = num(stats?.avg_risk_score, 0)
  const topThreatUser = stats?.top_threat && stats.top_threat !== 'None' ? stats.top_threat : null

  // Risk distribution computed from the real risky-users list — no invented series.
  const distribution = useMemo(() => {
    const bands = { critical: 0, high: 0, medium: 0, low: 0 }
    topThreats.forEach(u => { bands[riskBand(num(u.total_risk_score))] += 1 })
    return bands
  }, [topThreats])

  const activeSessions = useMemo(
    () => sessions.filter(u => sessionState(u.last_seen).key === 'active').length,
    [sessions],
  )

  /* ── Loading (first paint only) ────────────────────────────────────────── */
  if (loading && !lastUpdate) {
    return <LoadingState label="Loading security telemetry…" className="h-[60vh]" />
  }

  /* ── Column defs ───────────────────────────────────────────────────────── */

  const threatColumns = [
    {
      key: 'rank', header: '#', width: '48px',
      render: (_r, i) => <span className="font-mono text-on-surface-muted tabular-nums">{i + 1}</span>,
    },
    {
      key: 'user', header: 'User',
      render: (u) => (
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-on-surface truncate">{u.name || u.user || 'Unknown'}</span>
            <span className="font-mono text-[0.7rem] text-on-surface-muted flex-shrink-0">{u.user}</span>
          </div>
          <p className="text-[0.7rem] text-on-surface-muted truncate">
            {(u.role || 'Employee')}{u.department ? ` · ${u.department}` : ''}
          </p>
        </div>
      ),
    },
    {
      key: 'bar', header: 'Risk', width: '130px',
      render: (u) => <RiskBar score={num(u.total_risk_score)} className="h-1.5 max-w-[110px]" />,
    },
    {
      key: 'score', header: 'Score', numeric: true, width: '72px',
      render: (u) => (
        <span className="font-mono font-semibold tabular-nums" style={{ color: riskColor(num(u.total_risk_score)) }}>
          {num(u.total_risk_score).toFixed(1)}
        </span>
      ),
    },
    {
      key: 'level', header: 'Level', align: 'right', width: '104px',
      render: (u) => <RiskBadge level={u.risk_level || riskBand(num(u.total_risk_score))} showIcon />,
    },
  ]

  const sessionColumns = [
    {
      key: 'employee', header: 'Employee',
      render: (u) => {
        const score = num(u.risk_score)
        return (
          <div className="flex items-center gap-2.5">
            <span
              className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
              style={{
                color: riskColor(score),
                background: `color-mix(in srgb, ${riskColor(score)} 14%, transparent)`,
                border: `1px solid color-mix(in srgb, ${riskColor(score)} 32%, transparent)`,
              }}
            >
              {initial(u.name)}
            </span>
            <div className="min-w-0">
              <p className="font-medium text-on-surface leading-tight truncate">{u.name || 'Unknown'}</p>
              <p className="text-[0.65rem] text-on-surface-muted font-mono">{u.user_id}</p>
            </div>
          </div>
        )
      },
    },
    {
      key: 'role', header: 'Role · Dept',
      render: (u) => (
        <div className="min-w-0">
          <p className="text-on-surface truncate">{u.role || '—'}</p>
          <p className="text-[0.65rem] text-on-surface-muted truncate">{u.department || '—'}</p>
        </div>
      ),
    },
    {
      key: 'risk', header: 'Risk', width: '140px',
      render: (u) => {
        const score = num(u.risk_score)
        return (
          <div className="flex items-center gap-2">
            <RiskBar score={score} className="h-1.5 w-16" />
            <span className="font-mono text-xs tabular-nums" style={{ color: riskColor(score) }}>
              {score.toFixed(0)}
            </span>
          </div>
        )
      },
    },
    {
      key: 'app', header: 'Active App',
      render: (u) => {
        const app = cleanApp(u.last_active_app)
        return app ? (
          <span className="flex items-center gap-1.5 text-on-surface-variant">
            <Monitor size={12} className="text-on-surface-muted flex-shrink-0" />
            <span className="font-mono text-xs truncate max-w-[120px]" title={u.last_active_app}>{app}</span>
          </span>
        ) : <span className="text-on-surface-muted">—</span>
      },
    },
    {
      key: 'status', header: 'Status',
      render: (u) => {
        const s = sessionState(u.last_seen)
        return (
          <div>
            <span className="flex items-center gap-1.5">
              <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${s.dot}`} />
              <span className="text-on-surface-variant text-xs">{s.label}</span>
            </span>
            <p className="text-[0.65rem] text-on-surface-muted mt-0.5">{relativeTime(u.last_seen)}</p>
          </div>
        )
      },
    },
    {
      key: 'events', header: 'Events', numeric: true, width: '84px',
      render: (u) => <span className="font-mono tabular-nums">{num(u.event_count).toLocaleString()}</span>,
    },
    {
      key: 'action', header: '', align: 'right', width: '120px',
      render: (u) => (
        <button
          onClick={(e) => { e.stopPropagation(); navigate(`/forensics?user=${encodeURIComponent(u.user_id || '')}`) }}
          className="inline-flex items-center gap-1 text-xs text-primary hover:text-primary-container transition-colors"
        >
          <Eye size={13} /> Investigate
        </button>
      ),
    },
  ]

  const distTotal = distribution.critical + distribution.high + distribution.medium + distribution.low || 1

  return (
    <div className="space-y-6 animate-fade-in">
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-on-surface">Security Operations Center</h1>
          <p className="text-xs text-on-surface-muted mt-0.5">
            Insider-threat behavioral monitoring · refreshes every {POLL_MS / 1000}s
          </p>
        </div>
        <div className="flex items-center gap-3">
          {lastUpdate && (
            <span className="hidden sm:flex items-center gap-1.5 text-xs text-on-surface-muted font-mono">
              <Clock size={12} /> {lastUpdate.toLocaleTimeString()}
            </span>
          )}
          <span className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-success-dim/40 bg-success-dim/10">
            <span className="live-dot" />
            <span className="text-[0.7rem] font-mono font-semibold uppercase tracking-wider text-success">Live</span>
          </span>
          <Button variant="ghost" size="sm" icon={RefreshCw} onClick={loadData}>Refresh</Button>
        </div>
      </div>

      {/* ── Error banner (primary pipeline unreachable) ─────────────────── */}
      {error && (
        <div className="flex items-center gap-3 rounded-md border border-error-container/50 bg-error-container/15 px-4 py-3">
          <ServerCrash size={18} className="text-error flex-shrink-0" />
          <div className="min-w-0">
            <p className="text-sm font-medium text-error">Backend unavailable</p>
            <p className="text-xs text-on-surface-muted">
              The risk pipeline API isn't responding. Is the server running? Retrying automatically every {POLL_MS / 1000}s.
            </p>
          </div>
        </div>
      )}

      {/* ── KPI stat cards ──────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard
          icon={Users} accent="cyan" label="Monitored Users" value={totalUsers.toLocaleString()}
          subtitle={sessions.length > 0 ? `${activeSessions} live session${activeSessions === 1 ? '' : 's'}` : 'risk pipeline'}
        />
        <StatCard
          icon={ShieldAlert} accent="red" label="High-Risk Users" value={highRiskUsers.toLocaleString()}
          subtitle="risk score ≥ 50"
        />
        <StatCard
          icon={Activity} accent="amber" label="Total Events" value={totalEvents.toLocaleString()}
          subtitle={`${highRiskEvents.toLocaleString()} flagged anomalous`}
        />
        <StatCard
          icon={Gauge} accent={avgRisk >= 60 ? 'red' : avgRisk >= 40 ? 'amber' : 'green'}
          label="Avg Risk Score" value={avgRisk.toFixed(1)}
          subtitle="mean across users"
        />
        <StatCard
          icon={Crosshair} accent="red" label="Top Threat"
          value={topThreatUser || '—'}
          subtitle={topThreatUser ? 'highest-risk user' : 'none flagged'}
          className={topThreatUser ? 'cursor-pointer' : ''}
        />
      </div>

      {/* ── Top Threats + Recent Alerts ─────────────────────────────────── */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Top Threats (spans 2) */}
        <Panel padding="p-0" className="xl:col-span-2">
          <div className="p-5 pb-0">
            <SectionHeader
              icon={ShieldAlert} iconColor="text-error" title="Top Threats"
              subtitle="Highest-risk users from the behavioral pipeline"
              actions={
                <Button variant="ghost" size="sm" icon={ExternalLink} onClick={() => navigate('/users')}>
                  All users
                </Button>
              }
            />
          </div>
          <div className="p-2">
            <DataTable
              columns={threatColumns}
              rows={topThreats}
              rowKey={(u, i) => u.user || i}
              onRowClick={(u) => navigate(`/forensics?user=${encodeURIComponent(u.user || '')}`)}
              empty={
                <EmptyState
                  icon={Radar} title="No risk data"
                  description="The risk pipeline returned no ranked users yet."
                />
              }
            />
          </div>
        </Panel>

        {/* Recent Alerts */}
        <Panel padding="p-0">
          <div className="p-5 pb-3">
            <SectionHeader
              icon={AlertTriangle} iconColor="text-tertiary" title="Recent Alerts"
              subtitle="Latest anomalies"
              actions={
                <button
                  onClick={() => navigate('/alerts')}
                  className="text-xs text-primary hover:text-primary-container transition-colors flex items-center gap-1"
                >
                  View all <ExternalLink size={12} />
                </button>
              }
            />
          </div>

          {recentAlerts.length === 0 ? (
            <EmptyState
              icon={AlertTriangle} title="No alerts" description="No anomalies flagged right now."
            />
          ) : (
            <ul className="divide-y divide-surface-variant/60">
              {recentAlerts.map((a, i) => {
                const score = num(a.risk_score)
                const sev = a.severity || riskBand(score)
                return (
                  <li key={a.alert_id || i}>
                    <button
                      onClick={() => navigate(`/forensics?user=${encodeURIComponent(a.user || '')}`)}
                      className="w-full text-left px-5 py-3 hover:bg-surface-high transition-colors flex items-start gap-3"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <SeverityPill severity={sev} />
                          <span className="text-sm font-medium text-on-surface truncate">
                            {a.name || a.user || 'Unknown'}
                          </span>
                          <span className="text-[0.7rem] font-mono text-on-surface-muted flex-shrink-0">{a.user}</span>
                        </div>
                        <p className="text-xs text-on-surface-muted truncate">
                          {a.activity || a.mitre_technique || 'Behavioral anomaly detected'}
                        </p>
                        {cleanApp(a.active_app) && (
                          <span className="mt-1 flex items-center gap-1 text-[0.65rem] text-on-surface-muted font-mono">
                            <Monitor size={10} /> {cleanApp(a.active_app)}
                          </span>
                        )}
                      </div>
                      <div className="text-right flex-shrink-0">
                        <span
                          className="text-sm font-bold font-mono tabular-nums"
                          style={{ color: riskColor(score) }}
                        >
                          {Math.round(score)}
                        </span>
                        <p className="text-[0.65rem] text-on-surface-muted mt-0.5">{relativeTime(a.timestamp)}</p>
                      </div>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </Panel>
      </div>

      {/* ── Risk distribution (honest, computed from ranked users) ──────── */}
      {topThreats.length > 0 && (
        <Card>
          <SectionHeader
            icon={Radar} title="Risk Distribution"
            subtitle={`Band breakdown of the top ${topThreats.length} ranked users`}
          />
          <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { band: 'critical', label: 'Critical', count: distribution.critical },
              { band: 'high', label: 'High', count: distribution.high },
              { band: 'medium', label: 'Medium', count: distribution.medium },
              { band: 'low', label: 'Low', count: distribution.low },
            ].map(({ band, label, count }) => (
              <div key={band} className="well p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-on-surface-variant">{label}</span>
                  <span className="font-mono font-semibold tabular-nums text-on-surface">{count}</span>
                </div>
                <div className="track h-1.5">
                  <div
                    className="track-fill"
                    style={{ width: `${(count / distTotal) * 100}%`, background: riskColor(band === 'critical' ? 90 : band === 'high' ? 70 : band === 'medium' ? 50 : 20) }}
                  />
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* ── Live Employee Sessions (secondary; clean empty state) ───────── */}
      <Panel padding="p-0">
        <div className="p-5 pb-3">
          <SectionHeader
            icon={Activity} title="Live Employee Sessions"
            subtitle="Real-time endpoint telemetry"
            actions={
              sessions.length > 0 ? (
                <span className="flex items-center gap-3 text-xs">
                  <span className="flex items-center gap-1.5 text-success">
                    <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
                    {activeSessions} active
                  </span>
                  <span className="text-on-surface-muted font-mono">{sessions.length} total</span>
                </span>
              ) : null
            }
          />
        </div>

        <DataTable
          columns={sessionColumns}
          rows={sessions}
          rowKey={(u, i) => u.user_id || i}
          onRowClick={(u) => navigate(`/forensics?user=${encodeURIComponent(u.user_id || '')}`)}
          empty={
            <EmptyState
              icon={WifiOff}
              title="No live telemetry"
              description="No endpoint agent is currently streaming sessions. The risk-pipeline data above stays live regardless."
            />
          }
          className="px-1"
        />
      </Panel>

      {/* ── Telemetry integrity (secondary; only when available) ────────── */}
      {integrity && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="col-span-2 lg:col-span-1">
            <p className="text-xs text-on-surface-muted mb-1">Users Tracked (Telemetry)</p>
            <p className="text-2xl font-bold font-mono tabular-nums text-on-surface">{num(integrity.total_users)}</p>
            <p className="text-xs text-on-surface-muted mt-1">avg risk {num(integrity.avg_risk_score).toFixed(1)}</p>
          </Card>
          <Card>
            <p className="text-xs text-success mb-1">In Zone (Normal)</p>
            <p className="text-2xl font-bold font-mono tabular-nums text-success">{num(integrity.in_zone)}</p>
          </Card>
          <Card>
            <p className="text-xs text-tertiary mb-1">Anomalous</p>
            <p className="text-2xl font-bold font-mono tabular-nums text-tertiary">{num(integrity.anomalous)}</p>
          </Card>
          <Card>
            <p className="text-xs text-error mb-1">Critical</p>
            <p className="text-2xl font-bold font-mono tabular-nums text-error">{num(integrity.critical)}</p>
          </Card>
        </div>
      )}
    </div>
  )
}
