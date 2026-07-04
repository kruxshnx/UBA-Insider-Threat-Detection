import { useState, useEffect, useCallback } from 'react'
import {
  Cpu, ShieldAlert, Database, SlidersHorizontal, Info, RefreshCw,
  Trash2, CheckCircle2, XCircle, AlertTriangle, Monitor, Zap,
  HardDrive, Clock, Lock,
} from 'lucide-react'
import { Panel, SectionHeader, Button, LoadingState, EmptyState, Skeleton, useToast } from '../components/ui'
import { fetchModelStatus, clearCache } from '../services/api'

/* ── Honest, backend-derived constants ─────────────────────────────────────
 * These severity bands are the SAME thresholds the risk pipeline applies
 * server-side (src/api/services/data_loader.py). They are shown read-only
 * because they are defined in the backend, not editable from the UI. */
const SEVERITY_BANDS = [
  { level: 'critical', label: 'Critical', min: 80, badge: 'badge-critical', desc: 'Immediate investigation — likely insider action' },
  { level: 'high', label: 'High', min: 60, badge: 'badge-high', desc: 'Priority review — strong anomaly signal' },
  { level: 'medium', label: 'Medium', min: 40, badge: 'badge-medium', desc: 'Monitor — elevated but ambiguous behaviour' },
  { level: 'low', label: 'Low', min: 0, badge: 'badge-low', desc: 'Baseline — no action required' },
]
// Score at/above which an event is flagged as high-risk and raises an alert.
const ALERT_TRIGGER = 50

const APP_VERSION = '1.0.0'

// ── helpers ────────────────────────────────────────────────────────────────
const fmtBytes = (n) => {
  if (n == null || Number.isNaN(n)) return '—'
  if (n < 1024) return `${n} B`
  const units = ['KB', 'MB', 'GB']
  let v = n / 1024
  let i = 0
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++ }
  return `${v.toFixed(1)} ${units[i]}`
}

const fmtDate = (iso) => {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString([], { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

// ── small presentational bits ───────────────────────────────────────────────
function ErrorBanner({ children, onRetry }) {
  return (
    <div className="flex items-center gap-3 rounded-md border border-error/40 bg-error-container/25 px-4 py-3 text-sm text-error">
      <AlertTriangle size={16} className="flex-shrink-0" />
      <span className="flex-1">{children}</span>
      {onRetry && (
        <button
          onClick={onRetry}
          className="text-xs font-medium underline underline-offset-2 hover:text-on-surface transition-colors"
        >
          Retry
        </button>
      )}
    </div>
  )
}

function InfoRow({ icon: Icon, label, value, valueClass = 'text-on-surface' }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2">
      <span className="flex items-center gap-2 text-xs text-on-surface-muted">
        {Icon && <Icon size={13} aria-hidden="true" />}
        {label}
      </span>
      <span className={`text-xs font-mono tabular-nums ${valueClass}`}>{value}</span>
    </div>
  )
}

export default function Settings() {
  const toast = useToast()
  const addToast = toast?.addToast

  // Model status
  const [modelData, setModelData] = useState(null)
  const [modelsLoading, setModelsLoading] = useState(true)
  const [modelsError, setModelsError] = useState(false)

  // Cache clear (Admin)
  const [clearing, setClearing] = useState(false)
  const [lastCleared, setLastCleared] = useState(null)

  // App preferences (real, DOM-applied — no fake toggles)
  const [reducedMotion, setReducedMotion] = useState(false)

  const loadModels = useCallback(async () => {
    setModelsLoading(true)
    setModelsError(false)
    const data = await fetchModelStatus()
    // fetchModelStatus falls back to { models: [] } on failure; treat a total
    // absence of the models array as a hard error, empty array as "no models".
    if (!data || !Array.isArray(data.models)) {
      setModelsError(true)
      setModelData(null)
    } else {
      setModelData(data)
    }
    setModelsLoading(false)
  }, [])

  useEffect(() => { loadModels() }, [loadModels])

  // Apply reduced-motion preference to <body> (the design system honours the
  // .low-power-mode class defined in index.css). This is a genuine effect.
  useEffect(() => {
    document.body.classList.toggle('low-power-mode', reducedMotion)
    return () => document.body.classList.remove('low-power-mode')
  }, [reducedMotion])

  const handleClearCache = async () => {
    setClearing(true)
    const res = await clearCache()
    setClearing(false)
    if (res != null) {
      setLastCleared(new Date())
      addToast?.('Server cache cleared', 'success')
    } else {
      addToast?.('Cache clear failed — is the API running with Admin access?', 'error')
    }
  }

  const models = modelData?.models ?? []
  const availableModels = modelData?.available_models ?? models.filter((m) => m?.exists).length
  const totalModels = modelData?.total_models ?? models.length

  return (
    <div className="space-y-6 animate-fade-in max-w-5xl">
      {/* Page header */}
      <div>
        <h1 className="text-xl font-bold text-on-surface">Settings</h1>
        <p className="text-xs text-on-surface-muted mt-0.5">
          System configuration, model health and preferences. Only controls wired to a live
          endpoint are interactive — display sections are labelled read-only.
        </p>
      </div>

      {/* ── Model Status ─────────────────────────────────────────────────── */}
      <Panel padding="p-0">
        <div className="p-5">
          <SectionHeader
            icon={Cpu}
            title="Model Status"
            subtitle="Trained ML artifacts on the server — live from /api/models/status"
            actions={
              <div className="flex items-center gap-3">
                {!modelsLoading && !modelsError && (
                  <span className="text-xs font-mono tabular-nums text-on-surface-muted">
                    <span className={availableModels === totalModels ? 'text-success' : 'text-tertiary'}>
                      {availableModels}
                    </span>
                    /{totalModels} available
                  </span>
                )}
                <Button variant="ghost" size="sm" icon={RefreshCw} onClick={loadModels} disabled={modelsLoading}>
                  Refresh
                </Button>
              </div>
            }
          />
        </div>

        {modelsLoading ? (
          <div className="px-5 pb-5">
            <LoadingState label="Loading model status…" className="h-40" />
          </div>
        ) : modelsError ? (
          <div className="px-5 pb-5">
            <ErrorBanner onRetry={loadModels}>
              Backend unavailable — could not load model status. Is the API running?
            </ErrorBanner>
          </div>
        ) : models.length === 0 ? (
          <EmptyState
            icon={Cpu}
            title="No models registered"
            description="No trained model artifacts were reported by the backend. Run the training pipeline to populate this list."
          />
        ) : (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Status</th>
                  <th className="num">Size</th>
                  <th>Last Modified</th>
                </tr>
              </thead>
              <tbody>
                {models.map((m, i) => {
                  const ok = !!m?.exists
                  return (
                    <tr key={m?.name || m?.path || i}>
                      <td>
                        <div className="flex items-center gap-2.5">
                          <HardDrive size={14} className="text-on-surface-muted flex-shrink-0" />
                          <span className="text-on-surface font-medium">{m?.name || 'Unknown model'}</span>
                        </div>
                      </td>
                      <td>
                        {ok ? (
                          <span className="badge badge-low">
                            <CheckCircle2 size={11} /> Available
                          </span>
                        ) : (
                          <span className="badge badge-neutral">
                            <XCircle size={11} /> Missing
                          </span>
                        )}
                      </td>
                      <td className="num">{fmtBytes(m?.size_bytes)}</td>
                      <td className="text-on-surface-variant">{fmtDate(m?.last_modified)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {/* ── Alert Severity Thresholds (read-only, backend-defined) ────────── */}
      <Panel>
        <SectionHeader
          icon={ShieldAlert}
          title="Alert Severity Thresholds"
          subtitle="Risk-score bands the pipeline applies to classify events"
          actions={<span className="badge badge-neutral"><Lock size={11} /> Read-only</span>}
          divider
        />

        <div className="well p-3 mb-4 flex items-start gap-2.5">
          <Info size={14} className="text-info flex-shrink-0 mt-0.5" />
          <p className="text-xs text-on-surface-variant leading-relaxed">
            These bands are defined server-side in the scoring pipeline and are shown here for
            reference. An event is flagged as high-risk and raises an alert once its score reaches{' '}
            <span className="font-mono tabular-nums text-primary">{ALERT_TRIGGER}</span>.
          </p>
        </div>

        <div className="grid gap-2.5 sm:grid-cols-2">
          {SEVERITY_BANDS.map((b) => {
            const upper = SEVERITY_BANDS
              .filter((x) => x.min > b.min)
              .sort((a, c) => a.min - c.min)[0]
            const range = upper ? `${b.min}–${upper.min - 1}` : `${b.min}–100`
            return (
              <div
                key={b.level}
                className="well p-4 flex items-start justify-between gap-3"
              >
                <div className="min-w-0">
                  <span className={`badge ${b.badge} mb-2`}>{b.label}</span>
                  <p className="text-xs text-on-surface-muted leading-relaxed">{b.desc}</p>
                </div>
                <div className="text-right flex-shrink-0">
                  <div className="text-lg font-bold font-mono tabular-nums text-on-surface leading-none">
                    {range}
                  </div>
                  <div className="text-[0.6rem] uppercase tracking-wide text-on-surface-muted mt-1">
                    score
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </Panel>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* ── Cache Management (Admin) ───────────────────────────────────── */}
        <Panel>
          <SectionHeader
            icon={Database}
            title="Cache Management"
            subtitle="Clear server-side query & risk caches"
            actions={<span className="badge badge-info"><Lock size={11} /> Admin</span>}
            divider
          />

          <p className="text-xs text-on-surface-variant leading-relaxed mb-4">
            Forces the backend to re-read risk data and rebuild cached aggregates on the next
            request. This calls the real
            {' '}<span className="font-mono text-on-surface-muted">POST /api/admin/cache/clear</span>{' '}
            endpoint with an Admin role header.
          </p>

          <div className="flex items-center gap-3 flex-wrap">
            <Button variant="danger" icon={clearing ? undefined : Trash2} onClick={handleClearCache} disabled={clearing}>
              {clearing ? (
                <>
                  <RefreshCw size={14} className="animate-spin" /> Clearing…
                </>
              ) : (
                'Clear Cache'
              )}
            </Button>
            {lastCleared && (
              <span className="flex items-center gap-1.5 text-xs text-success font-mono">
                <CheckCircle2 size={13} /> Cleared {lastCleared.toLocaleTimeString()}
              </span>
            )}
          </div>
        </Panel>

        {/* ── App Preferences (real, local) ──────────────────────────────── */}
        <Panel>
          <SectionHeader
            icon={SlidersHorizontal}
            title="Preferences"
            subtitle="Local display options for this browser"
            divider
          />

          <div className="divide-y divide-surface-variant/60">
            {/* Theme — honestly labelled: the app is dark-only */}
            <div className="flex items-center justify-between gap-3 py-3">
              <div className="flex items-center gap-3 min-w-0">
                <div className="rounded-md bg-surface-high p-2 flex-shrink-0">
                  <Monitor size={15} className="text-primary" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm text-on-surface">Theme</p>
                  <p className="text-xs text-on-surface-muted">Dark mode is the only supported theme</p>
                </div>
              </div>
              <span className="badge badge-neutral">Dark</span>
            </div>

            {/* Reduced motion — genuinely toggles body.low-power-mode */}
            <div className="flex items-center justify-between gap-3 py-3">
              <div className="flex items-center gap-3 min-w-0">
                <div className="rounded-md bg-surface-high p-2 flex-shrink-0">
                  <Zap size={15} className="text-tertiary" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm text-on-surface">Reduce motion</p>
                  <p className="text-xs text-on-surface-muted">Disable animations & backdrop effects</p>
                </div>
              </div>
              <button
                role="switch"
                aria-checked={reducedMotion}
                aria-label="Reduce motion"
                onClick={() => setReducedMotion((v) => !v)}
                className={`relative w-11 h-6 rounded-full transition-colors flex-shrink-0 ${
                  reducedMotion ? 'bg-primary/40' : 'bg-surface-highest'
                }`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-on-surface transition-transform ${
                    reducedMotion ? 'translate-x-5' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>
          </div>

          <p className="text-[0.7rem] text-on-surface-muted mt-3 leading-relaxed">
            Preferences apply to this browser session only and are not persisted to the server.
          </p>
        </Panel>
      </div>

      {/* ── About / System Info ──────────────────────────────────────────── */}
      <Panel>
        <SectionHeader
          icon={Info}
          title="About"
          subtitle="Build and connectivity information"
          divider
        />
        <div className="grid gap-x-8 sm:grid-cols-2 divide-y sm:divide-y-0 divide-surface-variant/50">
          <div className="divide-y divide-surface-variant/50">
            <InfoRow icon={Info} label="Application" value="UBA Insider Threat Detection" valueClass="text-on-surface" />
            <InfoRow icon={HardDrive} label="Version" value={APP_VERSION} />
          </div>
          <div className="divide-y divide-surface-variant/50">
            <InfoRow
              icon={Cpu}
              label="Models available"
              value={modelsLoading ? '…' : modelsError ? '—' : `${availableModels}/${totalModels}`}
              valueClass={modelsError ? 'text-error' : 'text-on-surface'}
            />
            <div className="flex items-center justify-between gap-3 py-2">
              <span className="flex items-center gap-2 text-xs text-on-surface-muted">
                <Clock size={13} aria-hidden="true" />
                API status
              </span>
              {modelsLoading ? (
                <Skeleton className="h-4 w-16" />
              ) : modelsError ? (
                <span className="flex items-center gap-1.5 text-xs font-mono text-error">
                  <XCircle size={12} /> Unreachable
                </span>
              ) : (
                <span className="flex items-center gap-1.5 text-xs font-mono text-success">
                  <span className="live-dot" /> Connected
                </span>
              )}
            </div>
          </div>
        </div>
      </Panel>
    </div>
  )
}
