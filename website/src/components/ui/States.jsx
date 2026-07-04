import { Inbox } from 'lucide-react'
import { cn } from '../../lib/utils'

/**
 * Skeleton — a shimmering placeholder block.
 * @param {string} [className]  Size it with width/height utilities.
 * @example <Skeleton className="h-4 w-32" />
 */
export function Skeleton({ className = '' }) {
  return <div className={cn('skeleton', className)} aria-hidden="true" />
}

/**
 * SkeletonText — N shimmering lines (last one shorter).
 * @param {number} [lines=3]
 */
export function SkeletonText({ lines = 3, className = '' }) {
  return (
    <div className={cn('space-y-2', className)} aria-hidden="true">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} className={cn('h-3.5', i === lines - 1 ? 'w-2/3' : 'w-full')} />
      ))}
    </div>
  )
}

/**
 * LoadingState — a centered spinner + message for whole-panel loading.
 * @param {string} [label='Loading…']
 * @param {string} [className]  Usually a min-height, e.g. "h-64".
 * @example <LoadingState label="Loading telemetry…" className="h-64" />
 */
export function LoadingState({ label = 'Loading…', className = 'h-48' }) {
  return (
    <div className={cn('flex flex-col items-center justify-center gap-3 text-on-surface-muted', className)} role="status" aria-live="polite">
      <span
        className="w-6 h-6 rounded-full border-2 border-surface-variant border-t-primary animate-spin"
        aria-hidden="true"
      />
      <span className="text-sm">{label}</span>
    </div>
  )
}

/**
 * EmptyState — icon + message shown when there is no data.
 * @param {React.ComponentType} [icon=Inbox]
 * @param {string} title
 * @param {string} [description]
 * @param {React.ReactNode} [action]   Optional CTA button.
 * @param {string} [className]
 * @example <EmptyState title="No alerts" description="You're all caught up." />
 */
export function EmptyState({ icon: Icon = Inbox, title, description, action, className = '' }) {
  return (
    <div className={cn('flex flex-col items-center justify-center text-center py-12 px-6', className)}>
      <div className="rounded-2xl bg-surface-high p-3.5 mb-3">
        <Icon size={26} className="text-on-surface-muted" aria-hidden="true" />
      </div>
      <p className="text-sm font-medium text-on-surface">{title}</p>
      {description && <p className="text-xs text-on-surface-muted mt-1 max-w-xs">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
