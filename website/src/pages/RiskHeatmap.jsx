import { useState, useEffect, useMemo } from 'react'
import { RefreshCw, TrendingUp, AlertTriangle, UserCheck, Zap, Clock } from 'lucide-react'
import GlassCard from '../components/GlassCard'
import { GlowCard } from '../components/ui/spotlight-card'
import { fetchHeatmapData } from '../services/api'

const HOURS = Array.from({ length: 24 }, (_, i) => i)

const RISK_COLORS = [
  { max: 0,   color: '#0d1117' },
  { max: 10,  color: '#0c2d3d' },
  { max: 20,  color: '#0e4d6a' },
  { max: 35,  color: '#1a6f8c' },
  { max: 50,  color: '#06b6d4' },
  { max: 65,  color: '#fbbf24' },
  { max: 80,  color: '#f97316' },
  { max: 90,  color: '#ef4444' },
  { max: 101, color: '#b91c1c' },
]

const getHeatColor = (score) => {
  for (const { max, color } of RISK_COLORS) {
    if (score < max) return color
  }
  return '#b91c1c'
}

const getRiskLabel = (score) => {
  if (score >= 80) return 'Critical'
  if (score >= 60) return 'High'
  if (score >= 40) return 'Medium'
  if (score > 0)  return 'Low'
  return 'None'
}

export default function RiskHeatmap() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState(null)
  const [lastUpdate, setLastUpdate] = useState(null)
  const [hoveredCell, setHoveredCell] = useState(null)
  const [roleFilter, setRoleFilter] = useState('All')
  const [minScore, setMinScore] = useState(0)

  const load = async () => {
    setFetchError(null)
    try {
      const data = await fetchHeatmapData()
      if (!data || !data.rows) throw new Error('Empty response')
      setRows(data.rows)
      setLastUpdate(new Date())
    } catch (err) {
      setFetchError('Could not load heatmap data. Is the backend running?')
      setRows([])
    }
    setLoading(false)
  }

  useEffect(() => {
    load()
    const iv = setInterval(load, 30000)
    return () => clearInterval(iv)
  }, [])

  const roles = useMemo(() => ['All', ...new Set(rows.map(r => r.role).filter(Boolean))], [rows])

  const filteredRows = useMemo(() => rows
    .filter(r => (roleFilter === 'All' || r.role === roleFilter) && r.risk_score >= minScore),
    [rows, roleFilter, minScore]
  )

  const peakHour = useMemo(() => {
    if (!filteredRows.length) return '—'
    const totals = HOURS.map(h => filteredRows.reduce((s, r) => s + (r.hours[h] || 0), 0))
    const idx = totals.indexOf(Math.max(...totals))
    return `${String(idx).padStart(2, '0')}:00`
  }, [filteredRows])

  const peakHourIdx = useMemo(() => {
    if (!filteredRows.length) return -1
    const totals = HOURS.map(h => filteredRows.reduce((s, r) => s + (r.hours[h] || 0), 0))
    return totals.indexOf(Math.max(...totals))
  }, [filteredRows])

  const highestUser = useMemo(() => {
    if (!filteredRows.length) return { name: '—', id: '' }
    const top = filteredRows[0]
    return { name: top.name, id: top.user_id }
  }, [filteredRows])

  const totalEvents = useMemo(() =>
    filteredRows.reduce((s, r) => s + r.event_counts.reduce((a, b) => a + b, 0), 0),
    [filteredRows]
  )

  const avgPeakScore = useMemo(() => {
    if (!filteredRows.length || peakHourIdx < 0) return 0
    const vals = filteredRows.map(r => r.hours[peakHourIdx] || 0).filter(v => v > 0)
    return vals.length ? (vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1) : 0
  }, [filteredRows, peakHourIdx])

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
          <h1 className="text-xl font-bold text-on-surface">Behavioral Risk Heatmap</h1>
          <p className="text-xs text-text-muted mt-0.5">
            Mouse velocity · Keystroke dynamics · Active window — last 7 days · {filteredRows.length} users · {totalEvents.toLocaleString()} events
          </p>
        </div>
        <div className="flex items-center gap-3">
          {lastUpdate && (
            <span className="text-xs text-text-muted font-mono flex items-center gap-1">
              <Clock size={11} /> {lastUpdate.toLocaleTimeString()}
            </span>
          )}
          <button onClick={load} className="flex items-center gap-1.5 px-3 py-1.5 bg-primary/10 text-primary rounded-lg text-xs hover:bg-primary/20 transition-colors">
            <RefreshCw size={12} /> Refresh
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <GlowCard customSize glowColor="blue" className="flex items-center gap-4 p-5">
          <div className="bg-primary/10 rounded-xl p-3"><Clock size={20} className="text-primary" /></div>
          <div>
            <p className="text-xs text-on-surface-variant">Peak Risk Hour</p>
            <p className="text-2xl font-bold font-mono text-on-surface">{peakHour}</p>
            <p className="text-xs text-text-muted">avg score {avgPeakScore}</p>
          </div>
        </GlowCard>
        <GlowCard customSize glowColor="red" className="flex items-center gap-4 p-5">
          <div className="bg-error-container/30 rounded-xl p-3"><AlertTriangle size={20} className="text-error" /></div>
          <div>
            <p className="text-xs text-on-surface-variant">Highest Risk User</p>
            <p className="text-lg font-bold font-mono text-on-surface leading-tight">{highestUser.name}</p>
            <p className="text-xs text-text-muted font-mono">{highestUser.id}</p>
          </div>
        </GlowCard>
        <GlowCard customSize glowColor="orange" className="flex items-center gap-4 p-5">
          <div className="bg-tertiary-container/20 rounded-xl p-3"><Zap size={20} className="text-tertiary" /></div>
          <div>
            <p className="text-xs text-on-surface-variant">Total Events (7d)</p>
            <p className="text-2xl font-bold font-mono text-on-surface">{totalEvents.toLocaleString()}</p>
            <p className="text-xs text-text-muted">{filteredRows.length} monitored users</p>
          </div>
        </GlowCard>
      </div>

      {/* Scoring context */}
      <div className="px-1 text-[0.7rem] text-text-muted leading-relaxed border-l-2 border-primary/30 pl-3">
        <span className="text-on-surface-variant font-medium">How scores are computed: </span>
        Each cell is the average risk score for that user at that hour, derived from mouse velocity deviation,
        keystroke flight-time anomaly, and active-window productivity alignment — sampled every 5 s by the on-host agent.
        Role multipliers apply: Admin ×1.5 · Contractor ×1.2 · Employee ×1.0. After-hours activity amplified ×2×.
      </div>

      {/* Heatmap */}
      <GlassCard>
        {/* Filters */}
        <div className="flex flex-wrap items-center gap-4 mb-5">
          <h3 className="text-sm font-semibold text-on-surface flex-1">Hourly Risk Distribution — Real Telemetry</h3>
          <div className="flex items-center gap-3 flex-wrap">
            <label className="text-xs text-text-muted font-mono">Role:</label>
            <select
              value={roleFilter}
              onChange={e => setRoleFilter(e.target.value)}
              className="bg-surface-highest text-on-surface text-xs font-mono px-3 py-1.5 rounded-lg border border-outline-variant/20 focus:outline-none focus:border-primary/40"
            >
              {roles.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
            <label className="text-xs text-text-muted font-mono">Min risk:</label>
            <input
              type="range" min={0} max={100} step={5} value={minScore}
              onChange={e => setMinScore(Number(e.target.value))}
              className="w-24 accent-primary"
            />
            <span className="text-xs font-mono text-primary w-6">{minScore}</span>
          </div>
        </div>

        {fetchError ? (
          <div className="text-center py-16">
            <p className="text-sm text-red-400 mb-3">{fetchError}</p>
            <button onClick={load} className="flex items-center gap-1.5 px-4 py-2 bg-primary/10 text-primary rounded-lg text-xs hover:bg-primary/20 transition-colors mx-auto">
              <RefreshCw size={12} /> Retry
            </button>
          </div>
        ) : filteredRows.length === 0 ? (
          <div className="text-center py-16 text-text-muted text-sm">
            {minScore > 0
              ? `No users with risk score ≥ ${minScore}. Lower the Min Risk slider.`
              : 'No telemetry data in the last 7 days. Ensure the on-host agent is running.'}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <div className="min-w-[860px]">
              {/* Hour Headers */}
              <div className="flex mb-1" style={{ marginLeft: '9rem' }}>
                {HOURS.map(h => (
                  <div key={h} className={`flex-1 text-center text-[0.6rem] font-mono ${h === peakHourIdx ? 'text-yellow-400 font-bold' : 'text-text-muted'}`}>
                    {String(h).padStart(2, '0')}
                  </div>
                ))}
              </div>

              {/* Rows */}
              <div className="space-y-0.5">
                {filteredRows.map(row => (
                  <div key={row.user_id} className="flex items-center group">
                    {/* User label */}
                    <div className="w-36 flex-shrink-0 pr-3 text-right">
                      <p className="text-[0.7rem] font-medium text-on-surface truncate">{row.name}</p>
                      <p className="text-[0.6rem] font-mono text-text-muted">{row.user_id}</p>
                    </div>
                    {/* Hour cells */}
                    <div className="flex flex-1 gap-px">
                      {row.hours.map((score, h) => (
                        <div
                          key={h}
                          className={`flex-1 h-7 rounded-sm cursor-crosshair transition-all duration-100 ${h === peakHourIdx ? 'ring-1 ring-yellow-400/30' : ''} hover:ring-1 hover:ring-white/30 hover:scale-y-110`}
                          style={{ backgroundColor: getHeatColor(score) }}
                          onMouseEnter={() => setHoveredCell({
                            user: row.name, userId: row.user_id, role: row.role, dept: row.department,
                            hour: h, score, events: row.event_counts[h], userRisk: row.risk_score
                          })}
                          onMouseLeave={() => setHoveredCell(null)}
                        />
                      ))}
                    </div>
                    {/* Row peak hour + score */}
                    <div className="w-20 text-right pl-2 flex-shrink-0">
                      {(() => {
                        const maxScore = Math.max(...row.hours)
                        const peakH = row.hours.indexOf(maxScore)
                        return (
                          <div>
                            <span className={`text-xs font-mono font-bold ${row.risk_score >= 80 ? 'text-red-400' : row.risk_score >= 60 ? 'text-orange-400' : row.risk_score >= 40 ? 'text-yellow-400' : 'text-green-400'}`}>
                              {row.risk_score.toFixed(0)}
                            </span>
                            {maxScore > 0 && (
                              <p className="text-[0.55rem] text-text-muted font-mono">peak {String(peakH).padStart(2,'0')}h</p>
                            )}
                          </div>
                        )
                      })()}
                    </div>
                  </div>
                ))}
              </div>

              {/* X-axis label */}
              <div className="flex mt-2" style={{ marginLeft: '9rem' }}>
                <div className="flex-1 text-center text-[0.6rem] text-text-muted font-mono">← Hour of Day (24h) →</div>
              </div>
            </div>
          </div>
        )}

        {/* Tooltip */}
        {hoveredCell && (
          <div className="mt-3 p-3 bg-surface-high rounded-lg border border-outline-variant/20 text-xs font-mono flex flex-wrap gap-4">
            <div><span className="text-text-muted">User: </span><span className="text-primary font-semibold">{hoveredCell.user}</span> <span className="text-text-muted">({hoveredCell.userId})</span></div>
            <div><span className="text-text-muted">Hour: </span><span className="text-on-surface">{String(hoveredCell.hour).padStart(2,'0')}:00</span></div>
            <div><span className="text-text-muted">Avg Risk: </span><span className={`font-bold ${hoveredCell.score >= 80 ? 'text-red-400' : hoveredCell.score >= 60 ? 'text-orange-400' : hoveredCell.score >= 40 ? 'text-yellow-400' : 'text-green-400'}`}>{hoveredCell.score} — {getRiskLabel(hoveredCell.score)}</span></div>
            <div><span className="text-text-muted">Events: </span><span className="text-on-surface">{hoveredCell.events}</span></div>
            <div><span className="text-text-muted">Role: </span><span className="text-on-surface-variant">{hoveredCell.role} · {hoveredCell.dept}</span></div>
            <div><span className="text-text-muted">Overall Risk: </span><span className="text-on-surface">{hoveredCell.userRisk}</span></div>
          </div>
        )}

        {/* Legend */}
        <div className="flex items-center gap-2 mt-5 justify-center">
          <span className="text-[0.6rem] font-mono text-text-muted">0</span>
          <div className="flex gap-px rounded overflow-hidden">
            {RISK_COLORS.map((c, i) => (
              <div key={i} className="w-8 h-3" style={{ backgroundColor: c.color }} title={`< ${c.max}`} />
            ))}
          </div>
          <span className="text-[0.6rem] font-mono text-text-muted">100</span>
          <span className="text-[0.6rem] font-mono text-text-muted ml-4">Risk Score →</span>
        </div>
      </GlassCard>
    </div>
  )
}
