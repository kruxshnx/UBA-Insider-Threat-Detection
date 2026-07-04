import { ResponsiveContainer, AreaChart, Area, LineChart, Line, Tooltip } from 'recharts'
import { CHART } from '../../lib/utils'

/**
 * ChartTooltip — a themed recharts tooltip content renderer. Pass it to any
 * recharts <Tooltip content={<ChartTooltip />} />. It reads the standard
 * recharts payload and renders label + one row per series in the app style.
 *
 * @param {(label)=>string} [labelFormatter]
 * @param {(value,name)=>string} [valueFormatter]
 *
 * @example <Tooltip content={<ChartTooltip valueFormatter={(v)=>`${v} events`} />} />
 */
export function ChartTooltip({ active, payload, label, labelFormatter, valueFormatter }) {
  if (!active || !payload || payload.length === 0) return null
  return (
    <div className="custom-tooltip">
      {label != null && (
        <div className="text-[0.7rem] font-mono text-on-surface-muted mb-1">
          {labelFormatter ? labelFormatter(label) : label}
        </div>
      )}
      <div className="space-y-0.5">
        {payload.map((p, i) => (
          <div key={i} className="flex items-center gap-2 text-xs">
            <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: p.color || p.stroke || p.fill }} />
            <span className="text-on-surface-variant">{p.name}</span>
            <span className="ml-auto font-mono font-semibold text-on-surface tabular-nums">
              {valueFormatter ? valueFormatter(p.value, p.name) : p.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

/**
 * Sparkline — a tiny, axis-less trend chart for inline metrics.
 *
 * @param {Array<number|object>} data   Numbers, or objects with `dataKey`.
 * @param {string} [dataKey='value']
 * @param {string} [color]              Line/area colour (default primary).
 * @param {boolean} [area=true]         Fill under the line with a soft gradient.
 * @param {number|string} [height=40]
 *
 * @example <Sparkline data={[3,5,4,8,6,9]} color="#ff5a52" />
 */
export function Sparkline({ data = [], dataKey = 'value', color = CHART.primary, area = true, height = 40 }) {
  const series = data.map((d) => (typeof d === 'number' ? { [dataKey]: d } : d))
  const gid = `spark-${Math.random().toString(36).slice(2, 8)}`

  if (series.length === 0) return <div style={{ height }} />

  return (
    <div style={{ width: '100%', height }} aria-hidden="true">
      <ResponsiveContainer width="100%" height="100%">
        {area ? (
          <AreaChart data={series} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.35} />
                <stop offset="100%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <Area
              type="monotone"
              dataKey={dataKey}
              stroke={color}
              strokeWidth={2}
              fill={`url(#${gid})`}
              isAnimationActive={false}
              dot={false}
            />
          </AreaChart>
        ) : (
          <LineChart data={series} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
            <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2} dot={false} isAnimationActive={false} />
          </LineChart>
        )}
      </ResponsiveContainer>
    </div>
  )
}

/** Shared props for recharts axes so every chart matches the theme. */
export const axisProps = {
  tick: { fill: CHART.axis, fontSize: 11 },
  axisLine: { stroke: CHART.grid },
  tickLine: false,
}
