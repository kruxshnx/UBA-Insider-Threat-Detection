import { useState, useEffect, useMemo, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Users as UsersIcon,
  Search,
  RefreshCw,
  ShieldAlert,
  ArrowUpDown,
  ChevronRight,
  Fingerprint,
} from 'lucide-react'

import { fetchRiskyUsers } from '../services/api'
import {
  Card,
  Panel,
  SectionHeader,
  StatCard,
  RiskBadge,
  RiskBar,
  DataTable,
  EmptyState,
  Skeleton,
  Button,
} from '../components/ui'
import { riskBand, cn } from '../lib/utils'

/* Normalise a raw user record into a safe, uniform shape.
   Every field is guarded — the backend is being fixed concurrently, so
   `name`, `role`, `department`, `risk_level` may all be null/undefined. */
function normalizeUser(raw = {}) {
  const id = raw.user ?? raw.user_id ?? raw.id ?? '—'
  const score = Number(
    raw.total_risk_score ?? raw.risk_score ?? 0,
  )
  const safeScore = Number.isFinite(score) ? score : 0
  // Prefer the backend's own band; fall back to a computed one from the score.
  const level = String(raw.risk_level || riskBand(safeScore)).toLowerCase()
  return {
    id,
    name: raw.name || null,
    role: raw.role || null,
    department: raw.department || null,
    score: safeScore,
    level,
  }
}

const SORTS = [
  { key: 'risk-desc', label: 'Risk: high → low' },
  { key: 'risk-asc', label: 'Risk: low → high' },
  { key: 'name-asc', label: 'Name: A → Z' },
  { key: 'id-asc', label: 'User ID: A → Z' },
]

const LEVELS = ['all', 'critical', 'high', 'medium', 'low']

export default function Users() {
  const navigate = useNavigate()

  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  const [searchTerm, setSearchTerm] = useState('')
  const [levelFilter, setLevelFilter] = useState('all')
  const [sortKey, setSortKey] = useState('risk-desc')

  const loadData = useCallback(async ({ silent = false } = {}) => {
    if (silent) setRefreshing(true)
    else setLoading(true)
    try {
      // PRIMARY risk-pipeline data — always the 100 synthetic users incl. U105.
      const data = await fetchRiskyUsers(100, 'desc')
      const list = Array.isArray(data) ? data.map(normalizeUser) : []
      setUsers(list)
      setError(false)
    } catch (err) {
      console.error('Users: failed to load risky users:', err)
      setError(true)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  /* Rank is assigned by descending risk over the FULL list (stable identity),
     so a user's rank badge is consistent regardless of the active sort. */
  const rankedById = useMemo(() => {
    const rank = new Map()
    ;[...users]
      .sort((a, b) => b.score - a.score)
      .forEach((u, i) => rank.set(u.id, i + 1))
    return rank
  }, [users])

  const filteredSorted = useMemo(() => {
    const q = searchTerm.trim().toLowerCase()
    let out = users.filter((u) => {
      const matchesLevel = levelFilter === 'all' || u.level === levelFilter
      if (!matchesLevel) return false
      if (!q) return true
      // Guard every field — never call .toLowerCase() on null.
      const hay = [u.id, u.name, u.role, u.department]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
      return hay.includes(q)
    })

    out = [...out].sort((a, b) => {
      switch (sortKey) {
        case 'risk-asc':
          return a.score - b.score
        case 'name-asc':
          return (a.name || a.id).localeCompare(b.name || b.id)
        case 'id-asc':
          return String(a.id).localeCompare(String(b.id))
        case 'risk-desc':
        default:
          return b.score - a.score
      }
    })
    return out
  }, [users, searchTerm, levelFilter, sortKey])

  /* ── Honest, computed KPIs (no fabricated numbers) ── */
  const stats = useMemo(() => {
    const total = users.length
    const critical = users.filter((u) => u.level === 'critical').length
    const high = users.filter((u) => u.level === 'high').length
    const avg = total
      ? users.reduce((s, u) => s + u.score, 0) / total
      : 0
    return { total, critical, high, avg }
  }, [users])

  const goToForensics = useCallback(
    (u) => {
      if (!u?.id || u.id === '—') return
      navigate(`/forensics?user=${encodeURIComponent(u.id)}`)
    },
    [navigate],
  )

  const columns = [
    {
      key: 'rank',
      header: '#',
      width: '3.5rem',
      render: (u) => (
        <span className="font-mono tabular-nums text-on-surface-muted">
          {rankedById.get(u.id) ?? '—'}
        </span>
      ),
    },
    {
      key: 'user',
      header: 'User',
      render: (u) => {
        const initial = (u.name || u.id || 'U').charAt(0).toUpperCase()
        return (
          <div className="flex items-center gap-3 min-w-0">
            <span
              className={cn(
                'flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold font-mono',
                u.level === 'critical' && 'bg-error-container/25 text-error',
                u.level === 'high' && 'bg-tertiary-container/20 text-tertiary',
                u.level === 'medium' && 'bg-tertiary-container/15 text-tertiary',
                u.level === 'low' && 'bg-success-dim/25 text-success',
              )}
              aria-hidden="true"
            >
              {initial}
            </span>
            <div className="min-w-0">
              <p className="text-sm font-medium text-on-surface truncate">
                {u.name || 'Unknown user'}
              </p>
              <p className="text-xs font-mono text-on-surface-muted truncate">
                {u.id}
              </p>
            </div>
          </div>
        )
      },
    },
    {
      key: 'role',
      header: 'Role',
      render: (u) => (
        <span className="text-on-surface-variant">{u.role || '—'}</span>
      ),
    },
    {
      key: 'department',
      header: 'Department',
      render: (u) => (
        <span className="text-on-surface-variant">{u.department || '—'}</span>
      ),
    },
    {
      key: 'risk',
      header: 'Risk Score',
      width: '9rem',
      render: (u) => (
        <div className="flex items-center gap-2.5">
          <RiskBar score={u.score} className="h-1.5 flex-1 min-w-[64px]" />
          <span className="font-mono tabular-nums text-sm text-on-surface w-9 text-right">
            {u.score.toFixed(0)}
          </span>
        </div>
      ),
    },
    {
      key: 'level',
      header: 'Level',
      render: (u) => <RiskBadge level={u.level} showIcon />,
    },
    {
      key: 'go',
      header: '',
      width: '2.5rem',
      align: 'right',
      render: () => (
        <ChevronRight
          size={16}
          className="text-on-surface-muted"
          aria-hidden="true"
        />
      ),
    },
  ]

  return (
    <div className="space-y-6 animate-fade-in">
      {/* ── Page header ── */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="bg-primary/10 rounded-xl p-2.5 flex-shrink-0">
            <UsersIcon size={22} className="text-primary" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-on-surface tracking-tight">
              User Risk Leaderboard
            </h1>
            <p className="text-sm text-on-surface-muted mt-0.5">
              Every monitored user ranked by model-scored insider-threat risk.
            </p>
          </div>
        </div>
        <Button
          variant="ghost"
          icon={RefreshCw}
          onClick={() => loadData({ silent: true })}
          disabled={refreshing || loading}
          className={refreshing ? '[&_svg]:animate-spin' : undefined}
        >
          Refresh
        </Button>
      </div>

      {/* ── Error banner (non-blocking) ── */}
      {error && (
        <div
          className="flex items-center gap-3 rounded-md border border-error-container/55 bg-error-container/15 px-4 py-3 text-sm text-error"
          role="alert"
        >
          <ShieldAlert size={16} className="flex-shrink-0" aria-hidden="true" />
          <span>
            Backend unavailable — could not load user risk data. Is the API
            running?
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => loadData()}
            className="ml-auto"
          >
            Retry
          </Button>
        </div>
      )}

      {/* ── KPI row ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="h-[92px]">
              <Skeleton className="h-full w-full" />
            </Card>
          ))
        ) : (
          <>
            <StatCard
              icon="users"
              label="Ranked Users"
              value={stats.total}
              accent="cyan"
            />
            <StatCard
              icon="alert"
              label="Critical Risk"
              value={stats.critical}
              accent="red"
            />
            <StatCard
              icon="shield"
              label="High Risk"
              value={stats.high}
              accent="amber"
            />
            <StatCard
              icon="activity"
              label="Avg Risk Score"
              value={stats.avg.toFixed(1)}
              accent="blue"
            />
          </>
        )}
      </div>

      {/* ── Leaderboard panel ── */}
      <Panel padding="p-0">
        <div className="p-4 sm:p-5 border-b border-surface-variant">
          <SectionHeader
            icon={ShieldAlert}
            title="Risk Ranking"
            subtitle={
              loading
                ? 'Loading…'
                : `${filteredSorted.length} of ${stats.total} users`
            }
          />

          {/* Toolbar: search + filters */}
          <div className="mt-4 flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1 min-w-0">
              <Search
                size={16}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-muted pointer-events-none"
                aria-hidden="true"
              />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search by user ID, name, role, or department…"
                className="input w-full pl-9"
                aria-label="Search users"
              />
            </div>

            <div className="flex gap-3">
              <label className="relative">
                <span className="sr-only">Filter by risk level</span>
                <select
                  value={levelFilter}
                  onChange={(e) => setLevelFilter(e.target.value)}
                  className="input pr-8 capitalize cursor-pointer"
                >
                  {LEVELS.map((lvl) => (
                    <option key={lvl} value={lvl}>
                      {lvl === 'all' ? 'All levels' : lvl}
                    </option>
                  ))}
                </select>
              </label>

              <label className="relative flex items-center">
                <ArrowUpDown
                  size={14}
                  className="absolute left-2.5 text-on-surface-muted pointer-events-none"
                  aria-hidden="true"
                />
                <span className="sr-only">Sort users</span>
                <select
                  value={sortKey}
                  onChange={(e) => setSortKey(e.target.value)}
                  className="input pl-8 pr-8 cursor-pointer"
                >
                  {SORTS.map((s) => (
                    <option key={s.key} value={s.key}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>
        </div>

        {/* Table / states */}
        {loading ? (
          <div className="p-4 sm:p-5 space-y-3">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="flex items-center gap-4">
                <Skeleton className="h-8 w-8 rounded-lg flex-shrink-0" />
                <Skeleton className="h-4 flex-1" />
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-1.5 w-24" />
                <Skeleton className="h-5 w-16" />
              </div>
            ))}
          </div>
        ) : (
          <DataTable
            columns={columns}
            rows={filteredSorted}
            rowKey={(u) => u.id}
            onRowClick={goToForensics}
            empty={
              users.length === 0 ? (
                <EmptyState
                  icon={UsersIcon}
                  title={error ? 'No data available' : 'No ranked users'}
                  description={
                    error
                      ? 'The risk pipeline returned no users. Check that the API is running.'
                      : 'No users have been scored by the risk pipeline yet.'
                  }
                  action={
                    <Button
                      variant="ghost"
                      size="sm"
                      icon={RefreshCw}
                      onClick={() => loadData()}
                    >
                      Reload
                    </Button>
                  }
                />
              ) : (
                <EmptyState
                  icon={Search}
                  title="No matching users"
                  description="No users match your search or filter. Try broadening the criteria."
                  action={
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setSearchTerm('')
                        setLevelFilter('all')
                      }}
                    >
                      Clear filters
                    </Button>
                  }
                />
              )
            }
          />
        )}
      </Panel>

      {/* Footer hint */}
      {!loading && filteredSorted.length > 0 && (
        <p className="flex items-center gap-1.5 text-xs text-on-surface-muted">
          <Fingerprint size={13} aria-hidden="true" />
          Select a user to open their forensic timeline.
        </p>
      )}
    </div>
  )
}
