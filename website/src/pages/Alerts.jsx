import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  RefreshCw, CheckCircle, Search as SearchIcon, Eye, X, AlertTriangle,
  Clock, Monitor, User, Shield, ArrowUpDown, Bell, BellOff, ChevronDown, ChevronUp
} from 'lucide-react'
import { GlowCard } from '../components/ui/spotlight-card'
import { fetchAlerts } from '../services/api'

const getRiskLevel = (score) => {
  if (score >= 80) return 'critical'
  if (score >= 60) return 'high'
  if (score >= 40) return 'medium'
  return 'low'
}

const SEVERITY_STYLE = {
  critical: {
    border: 'border-l-red-500',
    bg: 'bg-red-500/5',
    dot: 'bg-red-500',
    badge: 'bg-red-500/15 text-red-400 border border-red-500/30',
    score: 'text-red-400',
    pulse: true,
  },
  high: {
    border: 'border-l-orange-400',
    bg: 'bg-orange-400/5',
    dot: 'bg-orange-400',
    badge: 'bg-orange-400/15 text-orange-400 border border-orange-400/30',
    score: 'text-orange-400',
    pulse: false,
  },
  medium: {
    border: 'border-l-yellow-400',
    bg: 'bg-yellow-400/5',
    dot: 'bg-yellow-400',
    badge: 'bg-yellow-400/15 text-yellow-400 border border-yellow-400/30',
    score: 'text-yellow-400',
    pulse: false,
  },
  low: {
    border: 'border-l-green-500',
    bg: 'bg-green-500/5',
    dot: 'bg-green-500',
    badge: 'bg-green-500/15 text-green-400 border border-green-500/30',
    score: 'text-green-400',
    pulse: false,
  },
}

const relTime = (ts) => {
  if (!ts) return '—'
  const diff = Math.floor((Date.now() - new Date(ts).getTime()) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return new Date(ts).toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

const TABS = ['All', 'Critical', 'High', 'Medium']
const SORT_OPTIONS = [
  { value: 'risk_desc', label: 'Highest Risk' },
  { value: 'time_desc', label: 'Newest First' },
  { value: 'time_asc',  label: 'Oldest First' },
]

const PAGE_SIZE = 25

const MITRE_TACTIC_NAMES = {
  'TA0010': 'Exfiltration', 'TA0009': 'Collection', 'TA0002': 'Execution',
  'TA0005': 'Defense Evasion', 'TA0006': 'Credential Access',
  'TA0008': 'Lateral Movement', 'TA0003': 'Persistence',
}
const MITRE_TECHNIQUE_NAMES = {
  'T1048': 'Exfil via Alt Protocol', 'T1567': 'Exfil to Cloud Storage',
  'T1560': 'Archive Collected Data', 'T1059': 'Command & Script Interpreter',
  'T1562': 'Impair Defenses', 'T1555': 'Credential Store Theft',
  'T1021': 'Remote Services', 'T1078': 'Valid Accounts (Persistence)',
  'T1119': 'Automated Collection',
}

const formatActivity = (alert) => {
  const app = alert.active_app
  const level = getRiskLevel(alert.risk_score || 0)
  if (app) {
    const appName = app.replace(/\.exe$/i, '')
    const sev = level === 'critical' ? 'Critical' : level === 'high' ? 'High-risk' : 'Suspicious'
    return `${sev} behavioral anomaly detected while using ${appName}`
  }
  return alert.activity || alert.description || 'Anomalous behavioral pattern detected'
}

export default function Alerts() {
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [lastRefresh, setLastRefresh] = useState(null)
  const [activeTab, setActiveTab] = useState('All')
  const [sortBy, setSortBy] = useState('risk_desc')
  const [statusFilter, setStatusFilter] = useState('active')
  const [searchQuery, setSearchQuery] = useState('')
  const [acknowledged, setAcknowledged] = useState(new Set())
  const [dismissed, setDismissed] = useState(new Set())
  const [page, setPage] = useState(1)
  const [expandedId, setExpandedId] = useState(null)
  const navigate = useNavigate()

  const load = async () => {
    const data = await fetchAlerts({ limit: 500 })
    setAlerts(data?.alerts || [])
    setLastRefresh(new Date())
    setLoading(false)
  }

  useEffect(() => {
    load()
    const iv = setInterval(load, 30000)
    return () => clearInterval(iv)
  }, [])

  const counts = useMemo(() => ({
    All:      alerts.length,
    Critical: alerts.filter(a => getRiskLevel(a.risk_score || 0) === 'critical').length,
    High:     alerts.filter(a => getRiskLevel(a.risk_score || 0) === 'high').length,
    Medium:   alerts.filter(a => getRiskLevel(a.risk_score || 0) === 'medium').length,
    avgScore: alerts.length
      ? (alerts.reduce((s, a) => s + (a.risk_score || 0), 0) / alerts.length).toFixed(1)
      : 0,
  }), [alerts])

  const filteredAlerts = useMemo(() => {
    let list = alerts.filter(a => {
      const level = getRiskLevel(a.risk_score || 0)
      if (activeTab !== 'All' && level !== activeTab.toLowerCase()) return false
      const q = searchQuery.toLowerCase()
      if (q && !((a.user || '').toLowerCase().includes(q)) && !((a.name || '').toLowerCase().includes(q))) return false
      const id = a.alert_id || a.id
      if (statusFilter === 'active' && (acknowledged.has(id) || dismissed.has(id))) return false
      if (statusFilter === 'acknowledged' && !acknowledged.has(id)) return false
      if (statusFilter === 'dismissed' && !dismissed.has(id)) return false
      return true
    })
    if (sortBy === 'time_desc') list = [...list].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
    else if (sortBy === 'time_asc') list = [...list].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
    return list
  }, [alerts, activeTab, searchQuery, statusFilter, acknowledged, dismissed, sortBy])

  const ackAll = () => {
    const ids = filteredAlerts.map(a => a.alert_id || a.id)
    setAcknowledged(prev => new Set([...prev, ...ids]))
  }

  const userAlertCounts = useMemo(() => {
    const map = {}
    alerts.forEach(a => { const uid = a.user || a.user_id || ''; map[uid] = (map[uid] || 0) + 1 })
    return map
  }, [alerts])

  const totalPages = Math.max(1, Math.ceil(filteredAlerts.length / PAGE_SIZE))

  const pagedAlerts = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE
    return filteredAlerts.slice(start, start + PAGE_SIZE)
  }, [filteredAlerts, page])

  useEffect(() => { setPage(1); setExpandedId(null) }, [activeTab, statusFilter, searchQuery, sortBy])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <RefreshCw size={28} className="text-primary animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-on-surface">Active Alerts</h1>
          <p className="text-xs text-text-muted mt-0.5">
            {alerts.length} total anomalous events · refreshes every 30s
          </p>
        </div>
        <div className="flex items-center gap-3">
          {lastRefresh && (
            <span className="text-xs text-text-muted font-mono flex items-center gap-1">
              <Clock size={11} /> {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          <button onClick={load} className="flex items-center gap-1.5 px-3 py-1.5 bg-primary/10 text-primary rounded-lg text-xs hover:bg-primary/20 transition-colors">
            <RefreshCw size={12} /> Refresh
          </button>
        </div>
      </div>

      {/* Stat Cards — clickable filters */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <button onClick={() => { setActiveTab('Critical'); setStatusFilter('all') }} className="text-left">
          <GlowCard customSize glowColor="red" className={`p-4 flex items-center gap-3 cursor-pointer hover:ring-1 hover:ring-red-500/40 transition-all ${activeTab === 'Critical' ? 'ring-1 ring-red-500/50' : ''}`}>
            <div className="bg-red-500/10 rounded-lg p-2.5"><AlertTriangle size={18} className="text-red-400" /></div>
            <div>
              <p className="text-xs text-text-muted">Critical</p>
              <p className="text-2xl font-bold font-mono text-red-400">{counts.Critical}</p>
            </div>
          </GlowCard>
        </button>
        <button onClick={() => { setActiveTab('High'); setStatusFilter('all') }} className="text-left">
          <GlowCard customSize glowColor="orange" className={`p-4 flex items-center gap-3 cursor-pointer hover:ring-1 hover:ring-orange-400/40 transition-all ${activeTab === 'High' ? 'ring-1 ring-orange-400/50' : ''}`}>
            <div className="bg-orange-400/10 rounded-lg p-2.5"><Shield size={18} className="text-orange-400" /></div>
            <div>
              <p className="text-xs text-text-muted">High</p>
              <p className="text-2xl font-bold font-mono text-orange-400">{counts.High}</p>
            </div>
          </GlowCard>
        </button>
        <button onClick={() => { setActiveTab('All'); setStatusFilter('active') }} className="text-left">
          <GlowCard customSize glowColor="blue" className={`p-4 flex items-center gap-3 cursor-pointer hover:ring-1 hover:ring-primary/40 transition-all ${activeTab === 'All' && statusFilter === 'active' ? 'ring-1 ring-primary/50' : ''}`}>
            <div className="bg-primary/10 rounded-lg p-2.5"><Bell size={18} className="text-primary" /></div>
            <div>
              <p className="text-xs text-text-muted">Total Alerts</p>
              <p className="text-2xl font-bold font-mono text-on-surface">{counts.All}</p>
            </div>
          </GlowCard>
        </button>
        <button onClick={() => { setActiveTab('All'); setStatusFilter('acknowledged') }} className="text-left">
          <GlowCard customSize glowColor="blue" className={`p-4 flex items-center gap-3 cursor-pointer hover:ring-1 hover:ring-green-500/40 transition-all ${statusFilter === 'acknowledged' ? 'ring-1 ring-green-500/50' : ''}`}>
            <div className="bg-primary/10 rounded-lg p-2.5"><BellOff size={18} className="text-green-400" /></div>
            <div>
              <p className="text-xs text-text-muted">Acknowledged</p>
              <p className="text-2xl font-bold font-mono text-green-400">{acknowledged.size}</p>
            </div>
          </GlowCard>
        </button>
      </div>

      {/* Filters Row */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Severity tabs */}
        <div className="flex bg-surface-mid rounded-lg overflow-hidden">
          {TABS.map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 text-xs font-medium transition-all ${
                activeTab === tab ? 'bg-primary/15 text-primary' : 'text-on-surface-variant hover:bg-surface-highest'
              }`}
            >
              {tab}
              <span className="ml-1.5 text-[0.6rem] font-mono opacity-60">{counts[tab] ?? ''}</span>
            </button>
          ))}
        </div>

        {/* Status */}
        <select
          value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
          className="bg-surface-highest text-on-surface text-xs font-mono px-3 py-2 rounded-lg border border-outline-variant/20 focus:outline-none focus:border-primary/40"
        >
          <option value="active">Active</option>
          <option value="acknowledged">Acknowledged</option>
          <option value="dismissed">Dismissed</option>
          <option value="all">All</option>
        </select>

        {/* Sort */}
        <div className="flex items-center gap-1.5 bg-surface-highest rounded-lg px-3 py-2 border border-outline-variant/20">
          <ArrowUpDown size={12} className="text-text-muted" />
          <select
            value={sortBy} onChange={e => setSortBy(e.target.value)}
            className="bg-transparent text-on-surface text-xs font-mono focus:outline-none"
          >
            {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>

        {/* Search */}
        <div className="relative flex-1 min-w-[160px] max-w-sm">
          <SearchIcon size={13} className="absolute left-3 top-2.5 text-text-muted" />
          <input
            type="text" placeholder="Search name or user ID..."
            value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
            className="w-full bg-surface-highest text-on-surface text-xs font-mono pl-8 pr-3 py-2 rounded-lg border border-outline-variant/20 focus:outline-none focus:border-primary/40"
          />
        </div>

        {/* Ack all button */}
        {filteredAlerts.length > 0 && statusFilter === 'active' && (
          <button onClick={ackAll} className="text-xs px-3 py-2 bg-surface-highest rounded-lg border border-outline-variant/20 text-on-surface-variant hover:text-on-surface transition-colors flex items-center gap-1.5">
            <CheckCircle size={12} /> Ack All ({filteredAlerts.length})
          </button>
        )}
      </div>

      {/* Count summary */}
      <div className="flex items-center justify-between">
        <p className="text-xs text-text-muted">
          Showing{' '}
          <span className="text-on-surface font-mono">{Math.min(page * PAGE_SIZE, filteredAlerts.length)}</span>
          {' '}of{' '}
          <span className="text-on-surface font-mono">{filteredAlerts.length}</span> alerts
          {searchQuery && <> matching <span className="text-primary">"{searchQuery}"</span></>}
        </p>
        {totalPages > 1 && (
          <span className="text-xs text-text-muted font-mono">Page {page} / {totalPages}</span>
        )}
      </div>

      {/* Alert Cards */}
      <div className="space-y-2.5">
        {pagedAlerts.length === 0 && (
          <div className="text-center py-16 text-text-muted text-sm">
            {searchQuery ? `No alerts matching "${searchQuery}"` : 'No alerts match your current filters.'}
          </div>
        )}
        {pagedAlerts.map((alert, i) => {
          const id = alert.alert_id || alert.id || i
          const score = alert.risk_score || 0
          const level = getRiskLevel(score)
          const sty = SEVERITY_STYLE[level]
          const isAcked = acknowledged.has(id)
          const isDismissed = dismissed.has(id)
          const displayName = alert.name || alert.user || `User ${i}`
          const userId = alert.user || alert.user_id || ''
          const isExpanded = expandedId === id
          const userCount = userAlertCounts[userId] || 1
          const mitreTacticName = alert.mitre_tactic ? (MITRE_TACTIC_NAMES[alert.mitre_tactic] || alert.mitre_tactic) : null
          const mitreTechName = alert.mitre_technique ? (MITRE_TECHNIQUE_NAMES[alert.mitre_technique] || alert.mitre_technique) : null

          return (
            <div key={id} className={`rounded-xl border-l-4 border border-outline-variant/10 transition-all ${sty.border} ${sty.bg} ${isAcked || isDismissed ? 'opacity-50' : ''}`}>
              <div className="p-4">
                <div className="flex items-start gap-4">
                  {/* Score column: number + bar + level label */}
                  <div className="flex-shrink-0 flex flex-col items-center gap-1 w-12">
                    <div className={`w-2.5 h-2.5 rounded-full ${sty.dot} ${sty.pulse ? 'animate-pulse' : ''}`} />
                    <span className={`text-xl font-bold font-mono leading-none ${sty.score}`}>{score.toFixed(0)}</span>
                    <div className="w-full bg-surface-highest rounded-full h-1">
                      <div
                        className={`h-1 rounded-full ${level === 'critical' ? 'bg-red-500' : level === 'high' ? 'bg-orange-400' : level === 'medium' ? 'bg-yellow-400' : 'bg-green-500'}`}
                        style={{ width: `${score}%` }}
                      />
                    </div>
                    <span className={`text-[0.5rem] font-mono uppercase tracking-wide ${sty.score}`}>{level}</span>
                  </div>

                  {/* Main content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className="text-sm font-bold text-on-surface">{displayName}</span>
                      <span className="text-xs text-text-muted font-mono">{userId}</span>
                      {userCount > 1 && (
                        <span className="text-[0.6rem] bg-primary/10 text-primary px-1.5 py-0.5 rounded-full font-mono">{userCount} alerts</span>
                      )}
                      {isAcked && <span className="text-[0.6rem] bg-green-500/15 text-green-400 px-2 py-0.5 rounded-full font-mono">✓ Acknowledged</span>}
                      {isDismissed && <span className="text-[0.6rem] bg-surface-highest text-text-muted px-2 py-0.5 rounded-full font-mono">Dismissed</span>}
                    </div>
                    <p className="text-xs text-on-surface-variant mb-2">{formatActivity(alert)}</p>
                    <div className="flex flex-wrap items-center gap-2">
                      {alert.active_app && (
                        <span className="flex items-center gap-1 text-[0.65rem] font-mono text-on-surface-variant bg-surface-highest px-2 py-0.5 rounded-md">
                          <Monitor size={10} /> {alert.active_app}
                        </span>
                      )}
                      {alert.role && (
                        <span className="flex items-center gap-1 text-[0.65rem] font-mono text-on-surface-variant bg-surface-highest px-2 py-0.5 rounded-md">
                          <User size={10} /> {alert.role}{alert.department ? ` · ${alert.department}` : ''}
                        </span>
                      )}
                      {mitreTacticName && (
                        <span
                          className="text-[0.65rem] font-mono text-tertiary bg-tertiary-container/15 px-2 py-0.5 rounded-full"
                          title={`${alert.mitre_tactic} · ${alert.mitre_technique}`}
                        >
                          ⚑ {mitreTacticName}{mitreTechName ? `: ${mitreTechName}` : ''}
                        </span>
                      )}
                      <span className="flex items-center gap-1 text-[0.65rem] font-mono text-text-muted ml-auto">
                        <Clock size={10} /> {relTime(alert.timestamp)}
                      </span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex flex-col items-end gap-2 flex-shrink-0 ml-2">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => navigate(`/forensics?user=${userId}`)}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-primary/10 text-primary border border-primary/20 rounded-lg text-xs font-medium hover:bg-primary/20 transition-colors"
                      >
                        <Eye size={13} /> Investigate
                      </button>
                      <button
                        onClick={() => setAcknowledged(prev => { const s = new Set(prev); s.add(id); return s })}
                        disabled={isAcked}
                        className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors border ${
                          isAcked
                            ? 'bg-green-500/10 text-green-400 border-green-500/20 cursor-default'
                            : 'bg-surface-highest text-on-surface-variant border-outline-variant/20 hover:bg-surface-high'
                        }`}
                      >
                        <CheckCircle size={13} /> {isAcked ? 'Acked' : 'Ack'}
                      </button>
                      <button
                        onClick={() => setDismissed(prev => { const s = new Set(prev); s.add(id); return s })}
                        title="Dismiss this alert"
                        className="p-1.5 rounded-lg bg-surface-highest text-text-muted hover:text-red-400 border border-outline-variant/20 transition-colors"
                      >
                        <X size={13} />
                      </button>
                    </div>
                    <button
                      onClick={() => setExpandedId(isExpanded ? null : id)}
                      className="flex items-center gap-1 text-[0.65rem] text-text-muted hover:text-on-surface transition-colors"
                    >
                      {isExpanded ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                      {isExpanded ? 'Hide details' : 'Show details'}
                    </button>
                  </div>
                </div>

                {/* Expanded detail panel */}
                {isExpanded && (
                  <div className="mt-3 pt-3 border-t border-outline-variant/15 grid grid-cols-2 sm:grid-cols-4 gap-3 text-[0.7rem]">
                    <div>
                      <p className="text-text-muted mb-0.5">Risk Score</p>
                      <p className={`font-mono font-bold ${sty.score}`}>{score.toFixed(1)} / 100 — {level.charAt(0).toUpperCase() + level.slice(1)}</p>
                    </div>
                    <div>
                      <p className="text-text-muted mb-0.5">Productivity Score</p>
                      <p className="font-mono text-on-surface-variant">
                        {alert.productivity_score != null ? `${(alert.productivity_score * 100).toFixed(0)}%` : '—'}
                      </p>
                    </div>
                    <div>
                      <p className="text-text-muted mb-0.5">Timestamp</p>
                      <p className="font-mono text-on-surface-variant">{alert.timestamp ? new Date(alert.timestamp).toLocaleString() : '—'}</p>
                    </div>
                    <div>
                      <p className="text-text-muted mb-0.5">Alert ID</p>
                      <p className="font-mono text-on-surface-variant break-all">{alert.alert_id || '—'}</p>
                    </div>
                    {alert.window_title && (
                      <div className="col-span-2">
                        <p className="text-text-muted mb-0.5">Active Window</p>
                        <p className="font-mono text-on-surface-variant truncate">{alert.window_title}</p>
                      </div>
                    )}
                    {alert.mitre_tactic && (
                      <div className="col-span-2">
                        <p className="text-text-muted mb-0.5">MITRE ATT&CK Classification</p>
                        <p className="font-mono text-tertiary">
                          {alert.mitre_tactic}{mitreTacticName ? ` (${mitreTacticName})` : ''}{' — '}{alert.mitre_technique}{mitreTechName ? ` (${mitreTechName})` : ''}
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-2 border-t border-outline-variant/10">
          <p className="text-xs text-text-muted">
            Showing {((page - 1) * PAGE_SIZE) + 1}–{Math.min(page * PAGE_SIZE, filteredAlerts.length)} of {filteredAlerts.length} alerts
          </p>
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1.5 text-xs bg-surface-highest border border-outline-variant/20 rounded-lg text-on-surface-variant hover:bg-surface-high disabled:opacity-40 disabled:cursor-default transition-colors"
            >
              ← Prev
            </button>
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              const p = Math.max(1, Math.min(totalPages - 4, page - 2)) + i
              return (
                <button key={p} onClick={() => setPage(p)}
                  className={`w-8 h-8 text-xs rounded-lg border transition-colors ${
                    p === page
                      ? 'bg-primary/15 text-primary border-primary/30 font-semibold'
                      : 'bg-surface-highest text-on-surface-variant border-outline-variant/20 hover:bg-surface-high'
                  }`}
                >
                  {p}
                </button>
              )
            })}
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-3 py-1.5 text-xs bg-surface-highest border border-outline-variant/20 rounded-lg text-on-surface-variant hover:bg-surface-high disabled:opacity-40 disabled:cursor-default transition-colors"
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
