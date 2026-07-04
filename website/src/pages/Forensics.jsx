import { useState, useEffect, useMemo, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import {
  RefreshCw, Search, Clock, ShieldAlert, Send, CheckCircle2, Activity,
  Mail, User as UserIcon, Fingerprint, Crosshair, Sparkles, AlertTriangle,
  ListTree, GitBranch, Info,
} from 'lucide-react'
import {
  Card, Panel, SectionHeader, RiskBadge, Button,
  EmptyState, LoadingState, Skeleton, ChartTooltip, axisProps,
} from '../components/ui'
import {
  fetchRiskyUsers, fetchUsers, fetchUserProfile, fetchTimeline,
  fetchUserRiskAnalysis, fetchRiskExplanation, fetchAlerts, submitAnalystFeedback,
} from '../services/api'
import { CHART, riskBand, riskColor, formatPercent } from '../lib/utils'

// ── MITRE tactic labels (display names for real TA#### codes from event data) ──
const MITRE_TACTIC_NAMES = {
  TA0001: 'Initial Access', TA0002: 'Execution', TA0003: 'Persistence',
  TA0004: 'Privilege Escalation', TA0005: 'Defense Evasion',
  TA0006: 'Credential Access', TA0007: 'Discovery', TA0008: 'Lateral Movement',
  TA0009: 'Collection', TA0010: 'Exfiltration', TA0011: 'Command & Control',
  TA0040: 'Impact',
}
const MITRE_TECHNIQUE_NAMES = {
  T1048: 'Exfil Over Alt Protocol', T1052: 'Exfil Over Physical Medium',
  T1567: 'Exfil to Cloud Storage', T1560: 'Archive Collected Data',
  T1119: 'Automated Collection', T1078: 'Valid Accounts', T1059: 'Command & Script',
  T1562: 'Impair Defenses', T1555: 'Credential Store Theft', T1021: 'Remote Services',
  T1485: 'Data Destruction',
}

// Human-readable labels for the pipeline's real risk-model features.
const FEATURE_LABELS = {
  far: 'File Access Rate',
  eds: 'Email Domain Spread',
  iav: 'Inter-Activity Variance',
  oaf: 'Off-hours Activity Factor',
  login_entropy: 'Login Entropy',
  file_count: 'File Operations',
  email_count: 'Emails Sent',
}

const relTime = (ts) => {
  if (!ts) return '—'
  const t = new Date(ts).getTime()
  if (Number.isNaN(t)) return '—'
  const diff = Math.floor((Date.now() - t) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return new Date(ts).toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

const num = (v, digits = 1) => {
  const n = Number(v)
  return Number.isFinite(n) ? n.toFixed(digits) : '—'
}

// Colour helper for row accents keyed off a 0–100 score, via risk tokens.
const scoreStripe = (score) => ({ borderLeftColor: riskColor(score) })

// ── Small primitives ─────────────────────────────────────────────────────────
function Metric({ label, value, sub, accentScore }) {
  const color = accentScore != null ? riskColor(accentScore) : undefined
  return (
    <div className="well p-3">
      <p className="text-[0.65rem] uppercase tracking-wide text-on-surface-muted">{label}</p>
      <p className="text-lg font-bold font-mono tabular-nums mt-0.5 text-on-surface" style={color ? { color } : undefined}>
        {value}
      </p>
      {sub && <p className="text-[0.65rem] text-on-surface-muted mt-0.5">{sub}</p>}
    </div>
  )
}

// ── Behavioral factor bars (real model features from daily history) ───────────
function BehavioralFactors({ features }) {
  const rows = useMemo(() => {
    if (!features) return []
    // Normalise each feature to a 0–100 bar for comparison. Ratios (0–1) scale
    // by 100; counts scale relative to the max count in the set.
    const ratioKeys = ['far', 'eds', 'iav', 'oaf', 'login_entropy']
    const countKeys = ['file_count', 'email_count']
    const maxCount = Math.max(1, ...countKeys.map((k) => Number(features[k]) || 0))
    const out = []
    for (const k of ratioKeys) {
      if (features[k] == null) continue
      const raw = Number(features[k]) || 0
      out.push({ key: k, label: FEATURE_LABELS[k] || k, raw: num(raw, 3), pct: Math.min(100, Math.max(0, raw <= 1 ? raw * 100 : raw)) })
    }
    for (const k of countKeys) {
      if (features[k] == null) continue
      const raw = Number(features[k]) || 0
      out.push({ key: k, label: FEATURE_LABELS[k] || k, raw: String(Math.round(raw)), pct: (raw / maxCount) * 100 })
    }
    return out
  }, [features])

  if (rows.length === 0) {
    return <EmptyState icon={ListTree} title="No behavioral factors" description="No scored daily features exist for this user yet." className="py-8" />
  }

  return (
    <div className="space-y-2.5">
      {rows.map((r) => (
        <div key={r.key}>
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-on-surface-variant">{r.label}</span>
            <span className="text-xs font-mono tabular-nums text-on-surface">{r.raw}</span>
          </div>
          <div className="track h-1.5">
            <div className="track-fill" style={{ width: `${r.pct}%`, background: 'linear-gradient(90deg, var(--color-primary-dim), var(--color-primary))' }} />
          </div>
        </div>
      ))}
    </div>
  )
}

// ── SHAP explanation (real feature attributions; omitted gracefully) ──────────
function ShapExplanation({ explanation }) {
  const rows = useMemo(() => {
    if (!explanation || typeof explanation !== 'object') return []
    const entries = Object.entries(explanation)
      .map(([k, v]) => ({ key: k, label: FEATURE_LABELS[k] || k, value: Number(v) || 0 }))
      .filter((e) => Number.isFinite(e.value))
    const max = Math.max(1e-9, ...entries.map((e) => Math.abs(e.value)))
    return entries
      .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
      .slice(0, 8)
      .map((e) => ({ ...e, pct: (Math.abs(e.value) / max) * 100, positive: e.value >= 0 }))
  }, [explanation])

  if (rows.length === 0) return null

  return (
    <div className="space-y-2.5">
      <p className="text-xs text-on-surface-muted">
        Feature contributions to this day&apos;s score (SHAP).
        <span className="text-error"> Red</span> pushes risk up,
        <span className="text-success"> green</span> pulls it down.
      </p>
      {rows.map((r) => (
        <div key={r.key}>
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-on-surface-variant">{r.label}</span>
            <span className="text-xs font-mono tabular-nums" style={{ color: r.positive ? CHART.risk.critical : CHART.risk.low }}>
              {r.positive ? '+' : '−'}{Math.abs(r.value).toFixed(3)}
            </span>
          </div>
          <div className="track h-1.5">
            <div className="track-fill" style={{ width: `${r.pct}%`, background: r.positive ? CHART.risk.critical : CHART.risk.low }} />
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function Forensics() {
  const [searchParams, setSearchParams] = useSearchParams()

  const [users, setUsers] = useState([])          // merged risk-pipeline + live users
  const [selectedId, setSelectedId] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')

  const [profile, setProfile] = useState(null)
  const [history, setHistory] = useState([])      // daily risk history (pipeline)
  const [timeline, setTimeline] = useState([])    // live telemetry events
  const [mitre, setMitre] = useState([])          // real MITRE tactics for user
  const [shap, setShap] = useState(null)          // SHAP explanation | null

  const [listLoading, setListLoading] = useState(true)
  const [userLoading, setUserLoading] = useState(false)
  const [listError, setListError] = useState(false)
  const [detailError, setDetailError] = useState(false)

  const [highRiskOnly, setHighRiskOnly] = useState(false)
  const [isFP, setIsFP] = useState(false)
  const [notes, setNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  // ── Load user roster (PRIMARY: risk pipeline; SECONDARY: live telemetry) ────
  useEffect(() => {
    let cancelled = false
    const init = async () => {
      setListLoading(true)
      const [risky, live] = await Promise.all([
        fetchRiskyUsers(200, 'desc'),
        fetchUsers(true).catch(() => []),
      ])
      if (cancelled) return

      const riskyArr = Array.isArray(risky) ? risky : []
      const liveArr = Array.isArray(live) ? live : []
      if (riskyArr.length === 0 && liveArr.length === 0) setListError(true)

      const liveById = new Map(liveArr.map((u) => [u.user_id, u]))
      // Base roster is the risk pipeline (always the full synthetic cohort).
      const merged = riskyArr.map((u) => {
        const id = u.user || u.user_id
        const l = liveById.get(id) || {}
        return {
          id,
          name: u.name || l.name || null,
          role: u.role || l.role || 'Employee',
          department: u.department || l.department || 'General',
          score: Number(u.total_risk_score ?? l.risk_score ?? 0) || 0,
          level: (u.risk_level || l.risk_level || riskBand(u.total_risk_score || 0)),
          email: l.email || null,
          eventCount: l.event_count ?? null,
          lastApp: l.last_active_app && l.last_active_app !== '—' ? l.last_active_app : null,
        }
      })
      // Add any live-only users not present in the pipeline roster.
      const known = new Set(merged.map((m) => m.id))
      for (const l of liveArr) {
        if (known.has(l.user_id)) continue
        merged.push({
          id: l.user_id,
          name: l.name || null,
          role: l.role || 'Employee',
          department: l.department || 'General',
          score: Number(l.risk_score ?? 0) || 0,
          level: l.risk_level || riskBand(l.risk_score || 0),
          email: l.email || null,
          eventCount: l.event_count ?? null,
          lastApp: l.last_active_app && l.last_active_app !== '—' ? l.last_active_app : null,
        })
      }
      merged.sort((a, b) => b.score - a.score)
      setUsers(merged)

      const param = searchParams.get('user')
      const initial = (param && merged.find((m) => m.id === param)) ? param : (merged[0]?.id || null)
      setSelectedId(initial)
      setListLoading(false)
    }
    init()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Load per-user detail whenever the selection changes ─────────────────────
  useEffect(() => {
    if (!selectedId) return
    let cancelled = false
    const load = async () => {
      setUserLoading(true)
      setDetailError(false)
      setSubmitted(false)
      setIsFP(false)
      setNotes('')
      setProfile(null); setHistory([]); setTimeline([]); setMitre([]); setShap(null)

      const [prof, analysis, tl, alertsRes] = await Promise.all([
        fetchUserProfile(selectedId),
        fetchUserRiskAnalysis(selectedId),
        fetchTimeline(selectedId, 300),
        fetchAlerts({ limit: 500 }),
      ])
      if (cancelled) return

      if (!prof && !analysis) setDetailError(true)
      setProfile(prof || null)

      const hist = Array.isArray(analysis?.history) ? analysis.history : []
      // history comes newest-first; keep chronological for the trend chart.
      const chrono = [...hist].sort((a, b) => String(a.date).localeCompare(String(b.date)))
      setHistory(chrono)

      setTimeline(Array.isArray(tl?.events) ? tl.events : [])

      // Derive real MITRE tactics for THIS user from alert data (dedup).
      const userAlerts = (alertsRes?.alerts || []).filter((a) => (a.user || a.user_id) === selectedId)
      const seen = new Set()
      const tactics = []
      for (const a of userAlerts) {
        const t = a.mitre_tactic
        if (!t || seen.has(t)) continue
        seen.add(t)
        tactics.push({ tactic: t, technique: a.mitre_technique || null })
      }
      setMitre(tactics)

      // SHAP for the most-recent scored day (omit gracefully if unavailable).
      const latest = chrono[chrono.length - 1]
      if (latest?.date) {
        const exp = await fetchRiskExplanation(selectedId, latest.date)
        if (!cancelled) setShap(exp?.explanation || null)
      }

      if (!cancelled) setUserLoading(false)
    }
    load()
    return () => { cancelled = true }
  }, [selectedId])

  const selectUser = useCallback((id) => {
    setSelectedId(id)
    const next = new URLSearchParams(searchParams)
    next.set('user', id)
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams])

  const filteredUsers = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    if (!q) return users
    return users.filter((u) =>
      u.id.toLowerCase().includes(q) || (u.name || '').toLowerCase().includes(q))
  }, [users, searchQuery])

  const selectedUser = useMemo(() => users.find((u) => u.id === selectedId) || null, [users, selectedId])

  // Prefer profile score; fall back to roster score.
  const riskScore = Number(profile?.total_risk_score ?? selectedUser?.score ?? 0) || 0
  const level = riskBand(riskScore)

  // Latest scored day → drives behavioral factors, SHAP date, feedback day.
  const latestDay = history.length ? history[history.length - 1] : null

  // Trend chart data (last 30 days of pipeline history).
  const trendData = useMemo(() =>
    history.slice(-30).map((h) => ({
      date: String(h.date).slice(5),
      score: Number(h.risk_score) || 0,
    })), [history])

  const filteredTimeline = useMemo(() =>
    highRiskOnly ? timeline.filter((e) => (e.risk_score || 0) >= 50) : timeline,
    [timeline, highRiskOnly])

  const anomalyCount = useMemo(() => timeline.filter((e) => e.is_anomaly).length, [timeline])

  const handleSubmitFeedback = async () => {
    if (!selectedId) return
    setSubmitting(true)
    const day = latestDay?.date || new Date().toISOString().split('T')[0]
    const res = await submitAnalystFeedback({ userId: selectedId, day, isFalsePositive: isFP, comments: notes })
    setSubmitting(false)
    setSubmitted(res != null)
  }

  const displayName = profile?.name || selectedUser?.name || selectedId || 'User'
  const initial = (displayName || 'U').charAt(0).toUpperCase()

  // ── Whole-page loading (initial roster) ─────────────────────────────────────
  if (listLoading) {
    return <LoadingState label="Loading forensic subjects…" className="h-96" />
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <Fingerprint size={20} className="text-primary flex-shrink-0" />
          <div className="min-w-0">
            <h1 className="text-xl font-bold text-on-surface truncate">Forensic Investigation</h1>
            <p className="text-xs text-on-surface-muted mt-0.5">
              Deep-dive on a selected subject · {users.length} subjects in scope
            </p>
          </div>
        </div>
      </div>

      {listError && (
        <div className="card border-error-container/50 bg-error-container/10 px-4 py-3 flex items-center gap-2.5 text-sm text-error">
          <AlertTriangle size={16} className="flex-shrink-0" />
          Backend unavailable — is the API running? Showing whatever data could be loaded.
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* ── Subject selector ───────────────────────────────────────────── */}
        <Panel padding="p-4" className="lg:col-span-1 h-fit">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-on-surface">Subjects</h3>
            <span className="text-[0.65rem] font-mono text-on-surface-muted">{filteredUsers.length}</span>
          </div>
          <div className="relative mb-3">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-muted" />
            <input
              type="text"
              placeholder="Search name or ID…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input w-full pl-8 font-mono text-xs"
              aria-label="Search subjects"
            />
          </div>
          <div className="space-y-1 max-h-[420px] overflow-y-auto pr-1">
            {filteredUsers.length === 0 && (
              <p className="text-xs text-on-surface-muted text-center py-6">No subjects match “{searchQuery}”.</p>
            )}
            {filteredUsers.map((u) => {
              const active = u.id === selectedId
              return (
                <button
                  key={u.id}
                  onClick={() => selectUser(u.id)}
                  aria-pressed={active}
                  className={`w-full text-left px-3 py-2 rounded-md transition-colors border ${
                    active
                      ? 'bg-primary/10 border-primary/30'
                      : 'bg-transparent border-transparent hover:bg-surface-high'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: riskColor(u.score) }} />
                    <span className={`text-xs font-medium truncate ${active ? 'text-primary' : 'text-on-surface'}`}>
                      {u.name || u.id}
                    </span>
                    <span className="ml-auto text-[0.65rem] font-mono tabular-nums text-on-surface-muted">
                      {u.score.toFixed(0)}
                    </span>
                  </div>
                  <span className="block text-[0.6rem] text-on-surface-muted font-mono mt-0.5 ml-3.5 truncate">
                    {u.id} · {u.role}
                  </span>
                </button>
              )
            })}
          </div>
        </Panel>

        {/* ── Subject profile ────────────────────────────────────────────── */}
        <div className="lg:col-span-3">
          {userLoading && !profile ? (
            <Card className="h-full">
              <div className="flex items-start gap-4">
                <Skeleton className="w-14 h-14 rounded-xl" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-5 w-48" />
                  <Skeleton className="h-3.5 w-64" />
                </div>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
                {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-16" />)}
              </div>
            </Card>
          ) : detailError ? (
            <Card className="h-full">
              <EmptyState
                icon={AlertTriangle}
                title="Could not load this subject"
                description="The profile and risk history endpoints did not respond. Is the API running?"
              />
            </Card>
          ) : (
            <Card className="h-full">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="flex items-center gap-3.5 min-w-0">
                  <div
                    className="w-14 h-14 rounded-xl flex items-center justify-center text-xl font-bold flex-shrink-0 border"
                    style={{
                      color: riskColor(riskScore),
                      borderColor: 'var(--color-surface-variant)',
                      background: 'var(--color-surface-low)',
                    }}
                  >
                    {initial}
                  </div>
                  <div className="min-w-0">
                    <h2 className="text-lg font-bold text-on-surface truncate">{displayName}</h2>
                    <p className="text-xs text-on-surface-muted font-mono truncate">
                      {selectedId} · {profile?.role || selectedUser?.role || '—'} · {profile?.department || selectedUser?.department || '—'}
                    </p>
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 mt-1">
                      {selectedUser?.email && (
                        <span className="text-[0.7rem] text-on-surface-muted flex items-center gap-1">
                          <Mail size={10} /> {selectedUser.email}
                        </span>
                      )}
                      {profile?.last_seen && (
                        <span className="text-[0.7rem] text-on-surface-muted flex items-center gap-1">
                          <Clock size={10} /> Last seen {relTime(profile.last_seen)}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="text-right flex-shrink-0">
                  <div className="text-4xl font-bold font-mono tabular-nums leading-none" style={{ color: riskColor(riskScore) }}>
                    {num(riskScore, 1)}
                  </div>
                  <p className="text-[0.65rem] text-on-surface-muted mt-1">Risk score / 100</p>
                  <div className="mt-1.5 flex justify-end">
                    <RiskBadge level={level} showIcon />
                  </div>
                  {profile?.rank != null && (
                    <p className="text-[0.65rem] text-on-surface-muted mt-1">Rank #{profile.rank} riskiest</p>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
                <Metric
                  label="Telemetry events"
                  value={(profile?.event_count ?? timeline.length).toLocaleString()}
                  sub="live agent stream"
                />
                <Metric
                  label="Anomalies"
                  value={anomalyCount.toLocaleString()}
                  sub="risk ≥ 50 events"
                  accentScore={anomalyCount > 0 ? 80 : 0}
                />
                <Metric
                  label="Avg risk"
                  value={num(profile?.avg_risk_score ?? 0, 1)}
                  sub="telemetry mean"
                  accentScore={profile?.avg_risk_score}
                />
                <Metric
                  label="Peak risk"
                  value={num(profile?.max_risk_score ?? 0, 1)}
                  sub="telemetry max"
                  accentScore={profile?.max_risk_score}
                />
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* ── Analysis grid ───────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Risk trend (pipeline daily history) */}
        <Panel padding="p-0" className="lg:col-span-2">
          <div className="p-5">
            <SectionHeader
              icon={Activity}
              title="Risk Score Trend"
              subtitle={
                trendData.length
                  ? `${trendData.length} days of scored history from the risk pipeline`
                  : 'No scored daily history for this subject'
              }
            />
          </div>
          <div className="px-2 pb-4">
            {userLoading && !trendData.length ? (
              <LoadingState label="Loading risk history…" className="h-56" />
            ) : trendData.length === 0 ? (
              <EmptyState
                icon={Activity}
                title="No risk history"
                description="The risk pipeline has not scored any days for this subject."
                className="h-56"
              />
            ) : (
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={trendData} margin={{ top: 8, right: 20, bottom: 4, left: -12 }}>
                    <defs>
                      <linearGradient id="fx-risk" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={CHART.risk.critical} stopOpacity={0.25} />
                        <stop offset="100%" stopColor={CHART.risk.critical} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} vertical={false} />
                    <XAxis {...axisProps} dataKey="date" tick={{ ...axisProps.tick, fontSize: 10 }} minTickGap={16} />
                    <YAxis {...axisProps} domain={[0, 100]} width={40} />
                    <Tooltip
                      content={<ChartTooltip valueFormatter={(v) => `${v} / 100`} />}
                      cursor={{ stroke: CHART.grid }}
                    />
                    <Line
                      type="monotone" dataKey="score" name="Risk"
                      stroke={CHART.risk.critical} strokeWidth={2}
                      dot={false} activeDot={{ r: 4 }} isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </Panel>

        {/* Behavioral factors (real model features of latest scored day) */}
        <Card>
          <SectionHeader
            icon={GitBranch}
            title="Behavioral Factors"
            subtitle={latestDay ? `Model features · ${latestDay.date}` : 'Latest scored day'}
            divider
          />
          {userLoading && !latestDay ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-6" />)}
            </div>
          ) : (
            <BehavioralFactors features={latestDay} />
          )}
        </Card>

        {/* SHAP explanation (real; whole card omitted if unavailable) */}
        {shap && Object.keys(shap).length > 0 ? (
          <Card>
            <SectionHeader
              icon={Sparkles}
              title="Model Explanation"
              subtitle="Why the model scored this subject"
              divider
            />
            <ShapExplanation explanation={shap} />
          </Card>
        ) : (
          <Card>
            <SectionHeader
              icon={Crosshair}
              title="MITRE ATT&CK"
              subtitle="Tactics observed in this subject's alerts"
              divider
            />
            {userLoading && mitre.length === 0 ? (
              <div className="flex flex-wrap gap-2">
                {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-7 w-32 rounded-full" />)}
              </div>
            ) : mitre.length === 0 ? (
              <EmptyState
                icon={Crosshair}
                title="No ATT&CK mappings"
                description="No alerts with MITRE tactics were recorded for this subject."
                className="py-8"
              />
            ) : (
              <div className="flex flex-wrap gap-2">
                {mitre.map((m) => {
                  const tName = MITRE_TACTIC_NAMES[m.tactic] || m.tactic
                  const techName = m.technique ? (MITRE_TECHNIQUE_NAMES[m.technique] || m.technique) : null
                  return (
                    <span
                      key={m.tactic}
                      className="badge badge-high"
                      title={`${m.tactic}${m.technique ? ` · ${m.technique}` : ''}`}
                    >
                      {m.tactic} · {tName}{techName ? ` — ${techName}` : ''}
                    </span>
                  )
                })}
              </div>
            )}
          </Card>
        )}
      </div>

      {/* If SHAP was shown above, MITRE gets its own full row so it is never dropped. */}
      {shap && Object.keys(shap).length > 0 && (
        <Card>
          <SectionHeader
            icon={Crosshair}
            title="MITRE ATT&CK"
            subtitle="Tactics observed in this subject's alerts"
            divider
          />
          {mitre.length === 0 ? (
            <EmptyState
              icon={Crosshair}
              title="No ATT&CK mappings"
              description="No alerts with MITRE tactics were recorded for this subject."
              className="py-8"
            />
          ) : (
            <div className="flex flex-wrap gap-2">
              {mitre.map((m) => {
                const tName = MITRE_TACTIC_NAMES[m.tactic] || m.tactic
                const techName = m.technique ? (MITRE_TECHNIQUE_NAMES[m.technique] || m.technique) : null
                return (
                  <span
                    key={m.tactic}
                    className="badge badge-high"
                    title={`${m.tactic}${m.technique ? ` · ${m.technique}` : ''}`}
                  >
                    {m.tactic} · {tName}{techName ? ` — ${techName}` : ''}
                  </span>
                )
              })}
            </div>
          )}
        </Card>
      )}

      {/* ── Event timeline (live telemetry; empty state when no agent) ────── */}
      <Panel padding="p-0">
        <div className="p-5">
          <SectionHeader
            icon={Clock}
            title="Event Timeline"
            subtitle={`${filteredTimeline.length} live telemetry events${highRiskOnly ? ' · high-risk only' : ''}`}
            actions={
              <label className="flex items-center gap-2 text-xs text-on-surface-muted cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={highRiskOnly}
                  onChange={(e) => setHighRiskOnly(e.target.checked)}
                  className="accent-[var(--color-primary)] w-3.5 h-3.5"
                />
                High-risk only (≥50)
              </label>
            }
          />
        </div>
        <div className="px-5 pb-5">
          {userLoading && timeline.length === 0 ? (
            <LoadingState label="Loading telemetry…" className="h-48" />
          ) : filteredTimeline.length === 0 ? (
            <EmptyState
              icon={Info}
              title="No telemetry events"
              description="No live telemetry has been recorded for this subject. Run the endpoint agent to populate the timeline. Risk scoring above still reflects the ML pipeline."
              className="py-10"
            />
          ) : (
            <div className="space-y-1.5 max-h-[480px] overflow-y-auto pr-1">
              {filteredTimeline.map((evt, i) => {
                const score = evt.risk_score || 0
                const d = evt.details || {}
                return (
                  <div
                    key={`${evt.timestamp || i}-${i}`}
                    className="well border-l-2 p-3"
                    style={scoreStripe(score)}
                  >
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <div className="flex items-center gap-2 min-w-0">
                        <Clock size={10} className="text-on-surface-muted flex-shrink-0" />
                        <span className="text-[0.65rem] font-mono text-on-surface-muted truncate">
                          {evt.timestamp ? new Date(evt.timestamp).toLocaleString() : `Event #${i + 1}`}
                        </span>
                        {evt.is_anomaly && (
                          <span className="badge badge-critical text-[0.55rem] py-0 px-1.5">Anomaly</span>
                        )}
                      </div>
                      <span className="text-xs font-mono font-bold tabular-nums flex-shrink-0" style={{ color: riskColor(score) }}>
                        {score.toFixed(1)}
                      </span>
                    </div>
                    <p className="text-xs text-on-surface-variant truncate">
                      {evt.activity || `Telemetry event #${i + 1}`}
                    </p>
                    {(d.mouse_velocity > 0 || d.keystroke_flight_ms > 0 || d.productivity > 0) && (
                      <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1.5 text-[0.6rem] font-mono text-on-surface-muted">
                        {d.mouse_velocity > 0 && <span>mouse {num(d.mouse_velocity, 1)} px/s</span>}
                        {d.keystroke_flight_ms > 0 && <span>flight {num(d.keystroke_flight_ms, 0)} ms</span>}
                        {d.productivity > 0 && <span>prod {formatPercent(d.productivity)}</span>}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </Panel>

      {/* ── Analyst feedback ─────────────────────────────────────────────── */}
      <Card>
        <SectionHeader
          icon={ShieldAlert}
          title="Analyst Feedback"
          subtitle={latestDay ? `Feedback applies to scored day ${latestDay.date}` : 'Record an investigation verdict'}
          divider
        />
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Investigation notes, findings, or escalation details…"
          className="input w-full h-24 resize-none font-mono text-xs"
          aria-label="Analyst notes"
        />
        <div className="flex flex-wrap items-center justify-between gap-3 mt-3">
          <label className="flex items-center gap-2 text-xs text-on-surface-variant cursor-pointer select-none">
            <input
              type="checkbox"
              checked={isFP}
              onChange={(e) => { setIsFP(e.target.checked); setSubmitted(false) }}
              className="accent-[var(--color-tertiary)] w-3.5 h-3.5"
            />
            <ShieldAlert size={13} className="text-tertiary" />
            Mark as false positive
          </label>
          <Button
            variant={submitted ? 'ghost' : 'primary'}
            icon={submitted ? CheckCircle2 : Send}
            onClick={handleSubmitFeedback}
            disabled={submitting || submitted || !selectedId}
          >
            {submitted ? 'Feedback recorded' : submitting ? 'Submitting…' : 'Submit feedback'}
          </Button>
        </div>
      </Card>
    </div>
  )
}
