import { useState, useEffect, useMemo, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  RefreshCw, CheckCircle, Search as SearchIcon, Eye, X, Clock, Monitor,
  User, ChevronDown, ChevronUp, ChevronLeft, ChevronRight, Bell, Crosshair,
  AlertCircle, Target,
} from 'lucide-react'
import {
  Panel, StatCard, RiskBadge, SeverityPill, RiskBar,
  Button, EmptyState, LoadingState, Skeleton,
} from '../components/ui'
import { riskBand } from '../lib/utils'
import { fetchAlerts } from '../services/api'

const PAGE_SIZE = 25
const REFRESH_MS = 30000

// The backend assigns severity labels from the risk score
// (Critical >= 80, High >= 60, Medium >= 50). These are the only
// server-supported filter values.
const SEVERITY_TABS = ['All', 'Critical', 'High', 'Medium']

// Map the backend's severity label -> the SeverityPill / RiskBadge band.
const SEVERITY_TO_BAND = { critical: 'critical', high: 'high', medium: 'medium', low: 'low' }

/** Best-effort band from an alert: prefer the server severity label, fall back to score. */
const alertBand = (alert) => {
  const sev = String(alert?.severity || '').toLowerCase()
  if (SEVERITY_TO_BAND[sev]) return SEVERITY_TO_BAND[sev]
  return riskBand(alert?.risk_score || 0)
}

const relTime = (ts) => {
  if (!ts) return '—'
  const t = new Date(ts).getTime()
  if (Number.isNaN(t)) return String(ts)
  const diff = Math.floor((Date.now() - t) / 1000)
  if (diff < 0) return 'just now'
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`
  return new Date(ts).toLocaleDateString([], { month: 'short', day: 'numeric' })
}

const absTime = (ts) => {
  if (!ts) return '—'
  const d = new Date(ts)
  return Number.isNaN(d.getTime()) ? String(ts) : d.toLocaleString()
}

/* ──────────────────────────────────────────────────────────────────────────
   Alert row
   ────────────────────────────────────────────────────────────────────────── */
function AlertRow({ alert, index, acked, dismissed, onAck, onDismiss, onInvestigate }) {
  const [open, setOpen] = useState(false)

  const id = alert.alert_id || `alert-${index}`
  const score = Number(alert.risk_score) || 0
  const band = alertBand(alert)
  const userId = alert.user || alert.user_id || ''
  const displayName = alert.name || userId || 'Unknown user'
  const activity = alert.activity || 'Anomalous behavioural pattern detected'

  // MITRE mapping comes straight from the data — never fabricated.
  const tactic = alert.mitre_tactic || null
  const technique = alert.mitre_technique || null
  const hasMitre = Boolean(tactic || technique)

  // productivity_score is only present on some payloads — show it only if real.
  const prod = alert.productivity_score
  const hasProd = prod != null && !Number.isNaN(Number(prod))

  const muted = acked || dismissed

  return (
    <div
      className={`card ${muted ? 'opacity-55' : 'card-hover'} p-4 transition-all`}
    >
      <div className="flex items-start gap-4">
        {/* Severity / score rail */}
        <div className="flex flex-col items-center gap-2 w-16 flex-shrink-0 pt-0.5">
          <SeverityPill severity={band} showIcon className="w-full justify-center" />
          <span className="text-lg font-bold font-mono tabular-nums leading-none text-on-surface">
            {score.toFixed(0)}
          </span>
          <RiskBar score={score} className="h-1 w-full" />
        </div>

        {/* Body */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="text-sm font-semibold text-on-surface truncate">{displayName}</span>
            {userId && (
              <span className="text-xs font-mono text-on-surface-muted">{userId}</span>
            )}
            {acked && (
              <span className="badge badge-low">
                <CheckCircle size={11} aria-hidden="true" /> Acknowledged
              </span>
            )}
            {dismissed && !acked && (
              <span className="badge badge-neutral">Dismissed</span>
            )}
          </div>

          <p className="text-xs text-on-surface-variant leading-relaxed mb-2 break-words">
            {activity}
          </p>

          <div className="flex flex-wrap items-center gap-2">
            {alert.active_app && (
              <span className="inline-flex items-center gap-1 text-[0.65rem] font-mono text-on-surface-variant bg-surface-high px-2 py-0.5 rounded-md">
                <Monitor size={10} aria-hidden="true" /> {alert.active_app}
              </span>
            )}
            {alert.role && (
              <span className="inline-flex items-center gap-1 text-[0.65rem] font-mono text-on-surface-variant bg-surface-high px-2 py-0.5 rounded-md">
                <User size={10} aria-hidden="true" />
                {alert.role}{alert.department ? ` · ${alert.department}` : ''}
              </span>
            )}
            {hasMitre && (
              <span
                className="inline-flex items-center gap-1 text-[0.65rem] font-mono text-tertiary bg-tertiary-container/20 px-2 py-0.5 rounded-md"
                title="MITRE ATT&CK classification"
              >
                <Target size={10} aria-hidden="true" />
                {[tactic, technique].filter(Boolean).join(' · ')}
              </span>
            )}
            {hasProd && (
              <span className="inline-flex items-center gap-1 text-[0.65rem] font-mono text-info bg-info/10 px-2 py-0.5 rounded-md">
                Productivity {Math.round(Number(prod) * (Number(prod) <= 1 ? 100 : 1))}%
              </span>
            )}
            <span className="inline-flex items-center gap-1 text-[0.65rem] font-mono text-on-surface-muted ml-auto">
              <Clock size={10} aria-hidden="true" /> {relTime(alert.timestamp)}
            </span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-col items-end gap-2 flex-shrink-0">
          <div className="flex items-center gap-1.5">
            {userId && (
              <Button size="sm" variant="primary" icon={Eye} onClick={() => onInvestigate(userId)}>
                Investigate
              </Button>
            )}
            <Button
              size="sm"
              variant="ghost"
              icon={CheckCircle}
              onClick={() => onAck(id)}
              disabled={acked}
              title={acked ? 'Acknowledged' : 'Acknowledge (session only)'}
            >
              {acked ? 'Acked' : 'Ack'}
            </Button>
            <button
              type="button"
              onClick={() => onDismiss(id)}
              title="Dismiss (session only)"
              className="icon-btn !w-8 !h-8 hover:text-error"
              aria-label="Dismiss alert"
            >
              <X size={14} aria-hidden="true" />
            </button>
          </div>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="inline-flex items-center gap-1 text-[0.65rem] text-on-surface-muted hover:text-on-surface transition-colors"
            aria-expanded={open}
          >
            {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            {open ? 'Hide details' : 'Details'}
          </button>
        </div>
      </div>

      {/* Expanded detail */}
      {open && (
        <div className="mt-3 pt-3 border-t border-surface-variant grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-3 text-[0.7rem]">
          <div>
            <p className="text-on-surface-muted mb-1">Risk score</p>
            <div className="flex items-center gap-2">
              <RiskBadge level={band} score={score.toFixed(0)} showIcon />
            </div>
          </div>
          <div>
            <p className="text-on-surface-muted mb-1">Severity</p>
            <p className="font-mono text-on-surface-variant">{alert.severity || band}</p>
          </div>
          <div>
            <p className="text-on-surface-muted mb-1">Status</p>
            <p className="font-mono text-on-surface-variant capitalize">{alert.status || 'open'}</p>
          </div>
          <div>
            <p className="text-on-surface-muted mb-1">Alert ID</p>
            <p className="font-mono text-on-surface-variant break-all">{alert.alert_id || '—'}</p>
          </div>
          <div className="col-span-2">
            <p className="text-on-surface-muted mb-1">Timestamp</p>
            <p className="font-mono text-on-surface-variant">{absTime(alert.timestamp)}</p>
          </div>
          {alert.window_title && (
            <div className="col-span-2">
              <p className="text-on-surface-muted mb-1">Active window</p>
              <p className="font-mono text-on-surface-variant truncate" title={alert.window_title}>
                {alert.window_title}
              </p>
            </div>
          )}
          {hasProd && (
            <div>
              <p className="text-on-surface-muted mb-1">Productivity</p>
              <p className="font-mono text-on-surface-variant">
                {Math.round(Number(prod) * (Number(prod) <= 1 ? 100 : 1))}%
              </p>
            </div>
          )}
          {hasMitre && (
            <div className="col-span-2 sm:col-span-4">
              <p className="text-on-surface-muted mb-1">MITRE ATT&amp;CK</p>
              <p className="font-mono text-tertiary">
                {tactic ? `Tactic ${tactic}` : ''}
                {tactic && technique ? '  ·  ' : ''}
                {technique ? `Technique ${technique}` : ''}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/* ──────────────────────────────────────────────────────────────────────────
   Skeleton row (loading)
   ────────────────────────────────────────────────────────────────────────── */
function SkeletonRow() {
  return (
    <div className="card p-4">
      <div className="flex items-start gap-4">
        <div className="flex flex-col items-center gap-2 w-16 flex-shrink-0">
          <Skeleton className="h-5 w-full" />
          <Skeleton className="h-4 w-8" />
          <Skeleton className="h-1 w-full" />
        </div>
        <div className="flex-1 space-y-2">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-3 w-3/4" />
          <div className="flex gap-2">
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-4 w-24" />
          </div>
        </div>
        <Skeleton className="h-8 w-24" />
      </div>
    </div>
  )
}

/* ──────────────────────────────────────────────────────────────────────────
   Page
   ────────────────────────────────────────────────────────────────────────── */
export default function Alerts() {
  const navigate = useNavigate()

  const [severity, setSeverity] = useState('All') // server-side filter
  const [page, setPage] = useState(0) // 0-indexed
  const [search, setSearch] = useState('') // client-side, on the loaded page

  const [data, setData] = useState({ alerts: [], total: 0 })
  const [counts, setCounts] = useState(null) // { Critical, High, Medium } — server totals
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [lastRefresh, setLastRefresh] = useState(null)

  // Session-only triage state (there is no persistence API for alert status).
  const [acked, setAcked] = useState(() => new Set())
  const [dismissed, setDismissed] = useState(() => new Set())

  const load = useCallback(async () => {
    setLoading(true)
    setError(false)
    const offset = page * PAGE_SIZE
    const sevParam = severity === 'All' ? undefined : severity

    // Main paged query + honest per-severity totals (cheap limit:1 count probes).
    const [res, critical, high, medium] = await Promise.all([
      fetchAlerts({ limit: PAGE_SIZE, offset, severity: sevParam }),
      fetchAlerts({ limit: 1, severity: 'Critical' }),
      fetchAlerts({ limit: 1, severity: 'High' }),
      fetchAlerts({ limit: 1, severity: 'Medium' }),
    ])

    // A null/failed main response signals the backend is unavailable.
    if (!res || !Array.isArray(res.alerts)) {
      setError(true)
      setData({ alerts: [], total: 0 })
    } else {
      setData({ alerts: res.alerts, total: Number(res.total) || res.alerts.length })
    }

    setCounts({
      Critical: Number(critical?.total) || 0,
      High: Number(high?.total) || 0,
      Medium: Number(medium?.total) || 0,
    })

    setLastRefresh(new Date())
    setLoading(false)
  }, [page, severity])

  useEffect(() => {
    load()
    const iv = setInterval(load, REFRESH_MS)
    return () => clearInterval(iv)
  }, [load])

  // Reset to first page when the severity filter changes.
  const changeSeverity = (tab) => {
    setSeverity(tab)
    setPage(0)
  }

  const totalCount = (counts?.Critical || 0) + (counts?.High || 0) + (counts?.Medium || 0)

  // Client-side search over the currently loaded page (name / user id).
  const visible = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return data.alerts
    return data.alerts.filter((a) =>
      String(a.user || '').toLowerCase().includes(q) ||
      String(a.name || '').toLowerCase().includes(q),
    )
  }, [data.alerts, search])

  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE))
  const pageWindow = useMemo(() => {
    const start = Math.max(0, Math.min(totalPages - 5, page - 2))
    return Array.from({ length: Math.min(5, totalPages) }, (_, i) => start + i)
  }, [totalPages, page])

  const handleAck = useCallback((id) => {
    setAcked((prev) => new Set(prev).add(id))
    setDismissed((prev) => {
      if (!prev.has(id)) return prev
      const next = new Set(prev)
      next.delete(id)
      return next
    })
  }, [])

  const handleDismiss = useCallback((id) => {
    setDismissed((prev) => new Set(prev).add(id))
  }, [])

  const handleInvestigate = useCallback(
    (userId) => navigate(`/forensics?user=${encodeURIComponent(userId)}`),
    [navigate],
  )

  const rangeStart = data.total === 0 ? 0 : page * PAGE_SIZE + 1
  const rangeEnd = Math.min((page + 1) * PAGE_SIZE, data.total)

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-bold text-on-surface flex items-center gap-2">
            <Bell size={20} className="text-primary" aria-hidden="true" />
            Active Alerts
          </h1>
          <p className="text-xs text-on-surface-muted mt-1">
            {error
              ? 'Alert queue unavailable'
              : `${totalCount.toLocaleString()} alert${totalCount === 1 ? '' : 's'} from risk-scored telemetry · auto-refresh 30s`}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {lastRefresh && !error && (
            <span className="text-xs text-on-surface-muted font-mono inline-flex items-center gap-1.5">
              <span className="live-dot" aria-hidden="true" />
              {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          <Button
            variant="ghost"
            size="sm"
            icon={RefreshCw}
            onClick={load}
            disabled={loading}
          >
            Refresh
          </Button>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div
          role="alert"
          className="flex items-start gap-3 rounded-md border border-error-container/55 bg-error-container/20 px-4 py-3"
        >
          <AlertCircle size={16} className="text-error flex-shrink-0 mt-0.5" aria-hidden="true" />
          <div className="text-sm">
            <p className="font-medium text-on-surface">Backend unavailable</p>
            <p className="text-xs text-on-surface-variant mt-0.5">
              Could not reach the alerts API. Is the backend running? Retrying automatically every 30s.
            </p>
          </div>
        </div>
      )}

      {/* Stat cards — real per-severity totals from the server */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={Crosshair}
          accent="red"
          label="Critical"
          value={counts ? counts.Critical.toLocaleString() : '—'}
          subtitle="Score ≥ 80"
        />
        <StatCard
          icon="alert"
          accent="amber"
          label="High"
          value={counts ? counts.High.toLocaleString() : '—'}
          subtitle="Score 60–79"
        />
        <StatCard
          icon="shield"
          accent="blue"
          label="Medium"
          value={counts ? counts.Medium.toLocaleString() : '—'}
          subtitle="Score 50–59"
        />
        <StatCard
          icon={Bell}
          accent="cyan"
          label="Total alerts"
          value={counts ? totalCount.toLocaleString() : '—'}
          subtitle="All open alerts"
        />
      </div>

      {/* Queue panel */}
      <Panel padding="p-0">
        <div className="p-4 border-b border-surface-variant flex flex-wrap items-center gap-3">
          {/* Severity segmented control (server-side filter) */}
          <div className="flex bg-surface-low border border-surface-variant rounded-md overflow-hidden">
            {SEVERITY_TABS.map((tab) => {
              const active = severity === tab
              const count =
                tab === 'All' ? totalCount : counts ? counts[tab] : null
              return (
                <button
                  key={tab}
                  type="button"
                  onClick={() => changeSeverity(tab)}
                  className={`px-3.5 py-1.5 text-xs font-medium transition-colors ${
                    active
                      ? 'bg-primary/15 text-primary'
                      : 'text-on-surface-variant hover:bg-surface-high hover:text-on-surface'
                  }`}
                >
                  {tab}
                  {count != null && (
                    <span className="ml-1.5 text-[0.6rem] font-mono tabular-nums opacity-60">
                      {count}
                    </span>
                  )}
                </button>
              )
            })}
          </div>

          {/* Search (scoped to the loaded page) */}
          <div className="relative flex-1 min-w-[180px] max-w-xs">
            <SearchIcon
              size={13}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-muted pointer-events-none"
              aria-hidden="true"
            />
            <input
              type="text"
              placeholder="Filter this page by user…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input w-full !pl-8 !py-1.5 font-mono text-xs"
              aria-label="Filter alerts on this page by user"
            />
          </div>

          <span className="text-xs text-on-surface-muted font-mono ml-auto tabular-nums">
            {data.total > 0 ? `${rangeStart}–${rangeEnd} of ${data.total}` : '0 alerts'}
          </span>
        </div>

        {/* List */}
        <div className="p-4 space-y-2.5">
          {loading && data.alerts.length === 0 ? (
            Array.from({ length: 6 }).map((_, i) => <SkeletonRow key={i} />)
          ) : error && data.alerts.length === 0 ? (
            <LoadingState label="Waiting for the alerts API…" className="h-56" />
          ) : visible.length === 0 ? (
            <EmptyState
              icon={search ? SearchIcon : CheckCircle}
              title={
                search
                  ? `No alerts on this page match “${search}”`
                  : severity === 'All'
                    ? 'No active alerts'
                    : `No ${severity.toLowerCase()} alerts`
              }
              description={
                search
                  ? 'Try a different user, or clear the filter to see the full page.'
                  : 'The queue is clear for this filter. New anomalies will appear here as telemetry is scored.'
              }
              action={
                search ? (
                  <Button variant="ghost" size="sm" onClick={() => setSearch('')}>
                    Clear filter
                  </Button>
                ) : null
              }
            />
          ) : (
            visible.map((alert, i) => {
              const id = alert.alert_id || `alert-${page}-${i}`
              return (
                <AlertRow
                  key={id}
                  alert={alert}
                  index={i}
                  acked={acked.has(id)}
                  dismissed={dismissed.has(id)}
                  onAck={handleAck}
                  onDismiss={handleDismiss}
                  onInvestigate={handleInvestigate}
                />
              )
            })
          )}
        </div>

        {/* Pagination */}
        {!error && totalPages > 1 && (
          <div className="p-4 border-t border-surface-variant flex items-center justify-between gap-3 flex-wrap">
            <p className="text-xs text-on-surface-muted font-mono tabular-nums">
              Page {page + 1} of {totalPages}
            </p>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="icon-btn !w-8 !h-8 disabled:opacity-40 disabled:pointer-events-none"
                aria-label="Previous page"
              >
                <ChevronLeft size={16} aria-hidden="true" />
              </button>
              {pageWindow.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setPage(p)}
                  className={`w-8 h-8 text-xs rounded-md border font-mono tabular-nums transition-colors ${
                    p === page
                      ? 'bg-primary/15 text-primary border-primary/30 font-semibold'
                      : 'bg-surface-low text-on-surface-variant border-surface-variant hover:bg-surface-high hover:text-on-surface'
                  }`}
                  aria-current={p === page ? 'page' : undefined}
                >
                  {p + 1}
                </button>
              ))}
              <button
                type="button"
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="icon-btn !w-8 !h-8 disabled:opacity-40 disabled:pointer-events-none"
                aria-label="Next page"
              >
                <ChevronRight size={16} aria-hidden="true" />
              </button>
            </div>
          </div>
        )}
      </Panel>
    </div>
  )
}
