import { useState, useEffect, useMemo, useCallback } from 'react'
import {
  RefreshCw, Clock, AlertTriangle, ShieldAlert, Grid3x3, ServerCrash, Info,
} from 'lucide-react'
import {
  Card, Panel, SectionHeader, Button, StatCard, RiskBadge,
  LoadingState, EmptyState,
} from '../components/ui'
import { CHART, riskBand, cn } from '../lib/utils'
import {
  fetchHeatmapData, fetchRiskyUsers, fetchRiskyEvents, fetchAlerts,
} from '../services/api'

/* ────────────────────────────────────────────────────────────────────────
   Risk Heatmap — user × hour matrix of risk.

   PRIMARY data: fetchHeatmapData() (per-user per-hour real risk scores).
   This endpoint can throw / be unavailable, so it is wrapped in try/catch.

   FALLBACK data: when the live telemetry heatmap is empty or errors, the
   matrix is derived from the risk-pipeline endpoints that always carry the
   100 synthetic users (incl. insider U105):
     - fetchRiskyUsers()  → the user roster + overall risk score
     - fetchAlerts()      → per-event timestamps bucketed into hour columns
     - fetchRiskyEvents() → additional high-risk events (timestamp/day)
   Cells with no observed activity stay at zero (the "quiet" tone).
   ──────────────────────────────────────────────────────────────────────── */

const HOURS = Array.from({ length: 24 }, (_, i) => i)

// Token-matched cell colours. Empty cells read as a faint slate well; active
// cells step Low → Medium → High → Critical using the design-system risk hues.
const EMPTY_CELL = 'var(--color-surface-variant)'
const bandColor = {
  low: CHART.risk.low,           // emerald
  medium: CHART.risk.medium,     // amber
  high: CHART.risk.high,         // orange
  critical: CHART.risk.critical, // red
}

// Colour a 0–100 cell. Intensity within a band is expressed via opacity so the
// grid still reads as a heat gradient while staying on-palette.
function cellStyle(score) {
  const s = Number(score) || 0
  if (s <= 0) return { backgroundColor: EMPTY_CELL, opacity: 0.35 }
  const band = riskBand(s)
  const color = bandColor[band]
  // 30% → 100% opacity ramp across the whole 1–100 range.
  const opacity = 0.3 + Math.min(1, s / 100) * 0.7
  return { backgroundColor: color, opacity }
}

function bandLabel(score) {
  const s = Number(score) || 0
  if (s <= 0) return 'None'
  return { low: 'Low', medium: 'Medium', high: 'High', critical: 'Critical' }[riskBand(s)]
}

const pad2 = (n) => String(n).padStart(2, '0')

// Pull an hour (0–23) out of whatever timestamp-ish field an event carries.
function hourOf(evt) {
  const raw = evt?.timestamp || evt?.time || evt?.date || evt?.day
  if (!raw) return null
  const d = new Date(raw)
  if (Number.isNaN(d.getTime())) return null
  return d.getHours()
}

// Normalise the shape returned by fetchHeatmapData() into rows the grid renders.
// Accepts either { rows:[{user_id,name,role,department,risk_score,hours[],event_counts[]}] }
// or a bare array of the same objects. Missing arrays are padded to 24 slots.
function normaliseHeatmapRows(data) {
  const raw = Array.isArray(data) ? data : Array.isArray(data?.rows) ? data.rows : []
  return raw
    .map((r) => {
      const hours = Array.isArray(r?.hours) ? r.hours : []
      const counts = Array.isArray(r?.event_counts) ? r.event_counts : []
      return {
        userId: r?.user_id || r?.user || '—',
        name: r?.name || r?.user || r?.user_id || 'Unknown',
        role: r?.role || null,
        department: r?.department || null,
        riskScore: Number(r?.risk_score ?? r?.total_risk_score ?? 0) || 0,
        hours: HOURS.map((h) => Number(hours[h]) || 0),
        counts: HOURS.map((h) => Number(counts[h]) || 0),
      }
    })
    .filter((r) => r.userId && r.userId !== '—')
}

// Build a user × hour matrix from the risk-pipeline endpoints (fallback path).
function deriveRowsFromPipeline(users, alerts, events) {
  const roster = new Map()

  const ensure = (id) => {
    if (!id) return null
    if (!roster.has(id)) {
      roster.set(id, {
        userId: id,
        name: id,
        role: null,
        department: null,
        riskScore: 0,
        hours: HOURS.map(() => 0),        // running sum of scores per hour
        counts: HOURS.map(() => 0),       // event count per hour
      })
    }
    return roster.get(id)
  }

  // Seed the roster from the risky-user list (gives name/role/dept + overall risk).
  ;(users || []).forEach((u) => {
    const id = u?.user
    if (!id) return
    const row = ensure(id)
    row.name = u.name || id
    row.role = u.role || null
    row.department = u.department || null
    row.riskScore = Number(u.total_risk_score ?? u.risk_score ?? 0) || 0
  })

  // Fold in per-event risk, bucketed by hour, from alerts + risky events.
  const fold = (list) => {
    ;(list || []).forEach((e) => {
      const id = e?.user
      if (!id) return
      const row = ensure(id)
      if (!row) return
      row.name = row.name === id ? (e.name || id) : row.name
      if (!row.role && e.role) row.role = e.role
      const h = hourOf(e)
      const score = Number(e.risk_score ?? e.total_risk_score ?? 0) || 0
      if (h != null) {
        row.counts[h] += 1
        // Keep the peak score for that hour (max reads better than a growing sum).
        row.hours[h] = Math.max(row.hours[h], score)
      }
    })
  }
  fold(alerts)
  fold(events)

  // If a user has an overall risk score but no bucketed hour data at all,
  // leave the row visible (grid shows a flat quiet strip) rather than dropping it.
  return Array.from(roster.values())
    .map((r) => ({ ...r, riskScore: r.riskScore || Math.max(...r.hours, 0) }))
    .sort((a, b) => b.riskScore - a.riskScore)
}

export default function RiskHeatmap() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)          // hard failure (banner)
  const [source, setSource] = useState('telemetry') // 'telemetry' | 'pipeline'
  const [lastUpdate, setLastUpdate] = useState(null)
  const [hovered, setHovered] = useState(null)

  const [roleFilter, setRoleFilter] = useState('All')
  const [minScore, setMinScore] = useState(0)

  const load = useCallback(async () => {
    setError(null)
    let heatmapRows = []
    let usedSource = 'telemetry'

    // 1) PRIMARY — the live telemetry heatmap (may throw).
    try {
      const data = await fetchHeatmapData()
      heatmapRows = normaliseHeatmapRows(data)
    } catch {
      heatmapRows = []
    }

    // 2) FALLBACK — derive from the always-populated risk-pipeline endpoints.
    if (heatmapRows.length === 0) {
      usedSource = 'pipeline'
      const [users, alertsRes, eventsRes] = await Promise.all([
        fetchRiskyUsers(100, 'desc').catch(() => []),
        fetchAlerts({ limit: 500 }).catch(() => ({ alerts: [] })),
        fetchRiskyEvents(500, 0).catch(() => ({ events: [] })),
      ])
      const alerts = Array.isArray(alertsRes?.alerts) ? alertsRes.alerts : []
      const events = Array.isArray(eventsRes?.events) ? eventsRes.events : []

      if (
        (Array.isArray(users) && users.length) ||
        alerts.length || events.length
      ) {
        heatmapRows = deriveRowsFromPipeline(users, alerts, events)
      } else {
        // Nothing anywhere — treat as a hard backend failure.
        setError('Backend unavailable — is the API running?')
      }
    }

    setRows(heatmapRows)
    setSource(usedSource)
    setLastUpdate(new Date())
    setLoading(false)
  }, [])

  useEffect(() => {
    load()
    const iv = setInterval(load, 30000)
    return () => clearInterval(iv)
  }, [load])

  const roles = useMemo(
    () => ['All', ...Array.from(new Set(rows.map((r) => r.role).filter(Boolean)))],
    [rows],
  )

  const filteredRows = useMemo(
    () =>
      rows.filter(
        (r) =>
          (roleFilter === 'All' || r.role === roleFilter) &&
          (r.riskScore || 0) >= minScore,
      ),
    [rows, roleFilter, minScore],
  )

  // Peak hour = the hour column with the highest summed risk across visible rows.
  const { peakHourIdx, peakLabel } = useMemo(() => {
    if (!filteredRows.length) return { peakHourIdx: -1, peakLabel: '—' }
    const totals = HOURS.map((h) =>
      filteredRows.reduce((s, r) => s + (r.hours[h] || 0), 0),
    )
    const idx = totals.indexOf(Math.max(...totals))
    return { peakHourIdx: idx, peakLabel: totals[idx] > 0 ? `${pad2(idx)}:00` : '—' }
  }, [filteredRows])

  const totalEvents = useMemo(
    () => filteredRows.reduce((s, r) => s + r.counts.reduce((a, b) => a + b, 0), 0),
    [filteredRows],
  )

  const highest = useMemo(() => {
    if (!filteredRows.length) return null
    return filteredRows.reduce((top, r) => (r.riskScore > (top?.riskScore || 0) ? r : top), null)
  }, [filteredRows])

  const criticalCount = useMemo(
    () => filteredRows.filter((r) => (r.riskScore || 0) >= 80).length,
    [filteredRows],
  )

  // ── Loading ───────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div className="h-8 w-64 skeleton" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-24 skeleton" />
          ))}
        </div>
        <Panel>
          <LoadingState label="Loading risk telemetry…" className="h-72" />
        </Panel>
      </div>
    )
  }

  const filtersActive = roleFilter !== 'All' || minScore > 0

  return (
    <div className="space-y-6 animate-fade-in">
      {/* ── Header ── */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-xl font-bold text-on-surface flex items-center gap-2">
            <Grid3x3 size={20} className="text-primary" aria-hidden="true" />
            Behavioral Risk Heatmap
          </h1>
          <p className="text-xs text-on-surface-muted mt-1">
            Per-user risk intensity across the 24-hour cycle ·{' '}
            <span className="font-mono tabular-nums">{filteredRows.length}</span> users ·{' '}
            <span className="font-mono tabular-nums">{totalEvents.toLocaleString()}</span> events
            {source === 'pipeline' && (
              <span className="ml-2 badge badge-neutral align-middle">
                <Info size={11} aria-hidden="true" /> derived from risk pipeline
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          {lastUpdate && (
            <span className="text-xs text-on-surface-muted font-mono tabular-nums flex items-center gap-1.5">
              <Clock size={12} aria-hidden="true" /> {lastUpdate.toLocaleTimeString()}
            </span>
          )}
          <Button variant="ghost" size="sm" icon={RefreshCw} onClick={load}>
            Refresh
          </Button>
        </div>
      </div>

      {/* ── Error banner (soft — keeps any partial data on screen) ── */}
      {error && (
        <div
          className="flex items-center gap-3 rounded-md border border-error-container/50 bg-error-container/15 px-4 py-3"
          role="alert"
        >
          <ServerCrash size={18} className="text-error flex-shrink-0" aria-hidden="true" />
          <div className="min-w-0">
            <p className="text-sm font-medium text-error">{error}</p>
            <p className="text-xs text-on-surface-muted mt-0.5">
              Showing no data. Confirm the API is reachable, then retry.
            </p>
          </div>
          <Button variant="ghost" size="sm" icon={RefreshCw} onClick={load} className="ml-auto">
            Retry
          </Button>
        </div>
      )}

      {/* ── Summary KPIs ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={Clock}
          accent="cyan"
          label="Peak Risk Hour"
          value={peakLabel}
          subtitle="highest aggregate risk"
        />
        <StatCard
          icon={ShieldAlert}
          accent="red"
          label="Highest-Risk User"
          value={highest ? Math.round(highest.riskScore) : '—'}
          subtitle={highest ? `${highest.name} · ${highest.userId}` : 'no data'}
        />
        <StatCard
          icon={AlertTriangle}
          accent="amber"
          label="Critical Users"
          value={criticalCount}
          subtitle="risk score ≥ 80"
        />
        <StatCard
          icon="activity"
          accent="green"
          label="Observed Events"
          value={totalEvents.toLocaleString()}
          subtitle={`${filteredRows.length} users in view`}
        />
      </div>

      {/* ── Heatmap panel ── */}
      <Panel padding="p-0">
        <div className="p-5">
          <SectionHeader
            icon={Grid3x3}
            title="Hourly Risk Distribution"
            subtitle="Each cell is the peak risk score for that user in that hour of the day"
            actions={
              <div className="flex items-center gap-3 flex-wrap">
                <label className="flex items-center gap-1.5 text-xs text-on-surface-muted font-mono">
                  Role
                  <select
                    value={roleFilter}
                    onChange={(e) => setRoleFilter(e.target.value)}
                    className="input !py-1 !px-2 text-xs font-mono"
                  >
                    {roles.map((r) => (
                      <option key={r} value={r}>{r}</option>
                    ))}
                  </select>
                </label>
                <label className="flex items-center gap-2 text-xs text-on-surface-muted font-mono">
                  Min risk
                  <input
                    type="range"
                    min={0}
                    max={100}
                    step={5}
                    value={minScore}
                    onChange={(e) => setMinScore(Number(e.target.value))}
                    className="w-24 accent-primary cursor-pointer"
                    aria-label="Minimum risk score filter"
                  />
                  <span className="text-primary tabular-nums w-6 text-right">{minScore}</span>
                </label>
              </div>
            }
          />
        </div>

        {/* Body: matrix or empty state */}
        {filteredRows.length === 0 ? (
          <div className="px-5 pb-8">
            <EmptyState
              icon={error ? ServerCrash : Grid3x3}
              title={
                error
                  ? 'No heatmap data'
                  : filtersActive
                    ? 'No users match the current filters'
                    : 'No risk telemetry yet'
              }
              description={
                error
                  ? 'Backend unavailable — is the API running?'
                  : filtersActive
                    ? 'Lower the minimum-risk slider or reset the role filter to see more users.'
                    : 'No per-user hourly risk is available. Once the pipeline scores events, the matrix will populate.'
              }
              action={
                filtersActive && !error ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => { setRoleFilter('All'); setMinScore(0) }}
                  >
                    Reset filters
                  </Button>
                ) : (
                  <Button variant="ghost" size="sm" icon={RefreshCw} onClick={load}>
                    Retry
                  </Button>
                )
              }
            />
          </div>
        ) : (
          <>
            <div className="table-scroll px-5">
              <div className="min-w-[880px] pb-1">
                {/* Hour axis header */}
                <div className="flex items-end mb-1">
                  <div className="w-40 flex-shrink-0 pr-3 text-[0.65rem] font-mono text-on-surface-muted uppercase tracking-wider">
                    User
                  </div>
                  <div className="flex flex-1 gap-px">
                    {HOURS.map((h) => (
                      <div
                        key={h}
                        className={cn(
                          'flex-1 text-center text-[0.6rem] font-mono tabular-nums',
                          h === peakHourIdx ? 'text-primary font-bold' : 'text-on-surface-muted',
                        )}
                      >
                        {pad2(h)}
                      </div>
                    ))}
                  </div>
                  <div className="w-16 flex-shrink-0 pl-2 text-right text-[0.65rem] font-mono text-on-surface-muted uppercase tracking-wider">
                    Risk
                  </div>
                </div>

                {/* Rows */}
                <div className="space-y-0.5">
                  {filteredRows.map((row) => (
                    <div key={row.userId} className="flex items-center group">
                      {/* User label */}
                      <div className="w-40 flex-shrink-0 pr-3 min-w-0">
                        <p className="text-[0.72rem] font-medium text-on-surface truncate leading-tight">
                          {row.name}
                        </p>
                        <p className="text-[0.6rem] font-mono text-on-surface-muted truncate">
                          {row.userId}
                          {row.role ? ` · ${row.role}` : ''}
                        </p>
                      </div>

                      {/* Hour cells */}
                      <div className="flex flex-1 gap-px">
                        {row.hours.map((score, h) => (
                          <div
                            key={h}
                            style={cellStyle(score)}
                            className={cn(
                              'flex-1 h-6 rounded-sm cursor-crosshair transition-all duration-100',
                              'hover:ring-2 hover:ring-primary/60 hover:z-10 hover:scale-y-125',
                              h === peakHourIdx && 'ring-1 ring-primary/25',
                            )}
                            onMouseEnter={() =>
                              setHovered({
                                name: row.name,
                                userId: row.userId,
                                role: row.role,
                                department: row.department,
                                hour: h,
                                score,
                                events: row.counts[h],
                                overall: row.riskScore,
                              })
                            }
                            onMouseLeave={() => setHovered(null)}
                            title={`${row.name} · ${pad2(h)}:00 · risk ${Math.round(score)} (${bandLabel(score)})`}
                          />
                        ))}
                      </div>

                      {/* Overall risk badge */}
                      <div className="w-16 flex-shrink-0 pl-2 flex justify-end">
                        <span
                          className={cn(
                            'text-xs font-mono font-bold tabular-nums',
                            row.riskScore >= 80 && 'text-risk-critical',
                            row.riskScore >= 60 && row.riskScore < 80 && 'text-risk-high',
                            row.riskScore >= 40 && row.riskScore < 60 && 'text-risk-medium',
                            row.riskScore < 40 && 'text-risk-low',
                          )}
                        >
                          {Math.round(row.riskScore)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>

                {/* X-axis caption */}
                <div className="flex mt-3">
                  <div className="w-40 flex-shrink-0" />
                  <div className="flex-1 text-center text-[0.6rem] font-mono text-on-surface-muted uppercase tracking-wider">
                    ← Hour of day (00–23) →
                  </div>
                  <div className="w-16 flex-shrink-0" />
                </div>
              </div>
            </div>

            {/* Hover detail — inline, token-styled */}
            <div className="px-5 pt-4">
              {hovered ? (
                <div className="well px-4 py-3 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs font-mono animate-fade-in">
                  <span>
                    <span className="text-on-surface-muted">User </span>
                    <span className="text-primary font-semibold">{hovered.name}</span>{' '}
                    <span className="text-on-surface-muted">({hovered.userId})</span>
                  </span>
                  <span>
                    <span className="text-on-surface-muted">Hour </span>
                    <span className="text-on-surface tabular-nums">{pad2(hovered.hour)}:00</span>
                  </span>
                  <span className="flex items-center gap-2">
                    <span className="text-on-surface-muted">Risk</span>
                    <RiskBadge
                      level={riskBand(hovered.score)}
                      score={Math.round(hovered.score)}
                      showIcon
                    />
                    <span className="text-on-surface-muted">({bandLabel(hovered.score)})</span>
                  </span>
                  <span>
                    <span className="text-on-surface-muted">Events </span>
                    <span className="text-on-surface tabular-nums">{hovered.events}</span>
                  </span>
                  {(hovered.role || hovered.department) && (
                    <span>
                      <span className="text-on-surface-muted">Context </span>
                      <span className="text-on-surface-variant">
                        {[hovered.role, hovered.department].filter(Boolean).join(' · ')}
                      </span>
                    </span>
                  )}
                  <span>
                    <span className="text-on-surface-muted">Overall risk </span>
                    <span className="text-on-surface tabular-nums">{Math.round(hovered.overall)}</span>
                  </span>
                </div>
              ) : (
                <div className="well px-4 py-3 text-xs text-on-surface-muted font-mono">
                  Hover a cell to inspect that user-hour.
                </div>
              )}
            </div>

            {/* Legend */}
            <div className="px-5 pt-4 pb-5">
              <div className="flex flex-wrap items-center gap-x-6 gap-y-3 justify-between">
                {/* Gradient scale */}
                <div className="flex items-center gap-2">
                  <span className="text-[0.65rem] font-mono text-on-surface-muted">Low risk</span>
                  <div className="flex rounded-sm overflow-hidden border border-surface-variant">
                    {[8, 25, 45, 65, 82, 95].map((s) => (
                      <div key={s} className="w-7 h-3.5" style={cellStyle(s)} title={`≈ ${s}`} />
                    ))}
                  </div>
                  <span className="text-[0.65rem] font-mono text-on-surface-muted">Critical</span>
                  <span className="ml-2 text-[0.6rem] font-mono text-on-surface-muted">Risk score →</span>
                </div>

                {/* Band key (icon + label pairs) */}
                <div className="flex flex-wrap items-center gap-2">
                  <RiskBadge level="low" showIcon />
                  <RiskBadge level="medium" showIcon />
                  <RiskBadge level="high" showIcon />
                  <RiskBadge level="critical" showIcon />
                </div>
              </div>
            </div>
          </>
        )}
      </Panel>

      {/* Scoring context — honest, no fabricated multipliers */}
      <Card padding="p-4" className="border-l-2 border-l-primary/40">
        <p className="text-xs text-on-surface-variant leading-relaxed">
          <span className="font-medium text-on-surface">How to read this: </span>
          each cell is the peak risk score for a user during that hour of the day, so hot columns
          reveal when suspicious behavior clusters (e.g. after-hours activity) and hot rows surface
          the users driving overall risk.
          {source === 'pipeline'
            ? ' Live telemetry was unavailable, so the matrix is derived from scored risk-pipeline events and alerts — hours come from event timestamps where present.'
            : ' Values are streamed from the on-host behavioral telemetry heatmap endpoint.'}
        </p>
      </Card>
    </div>
  )
}
