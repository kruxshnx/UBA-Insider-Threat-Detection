import { useEffect, useState } from 'react'
import { Routes, Route, Navigate, NavLink, useLocation } from 'react-router-dom'
import {
  Shield,
  LayoutDashboard,
  Thermometer,
  Fingerprint,
  AlertTriangle,
  Users as UsersIcon,
  Settings as SettingsIcon,
  Bell,
  Menu,
  X,
} from 'lucide-react'

import Dashboard from './pages/Dashboard'
import RiskHeatmap from './pages/RiskHeatmap'
import Forensics from './pages/Forensics'
import Alerts from './pages/Alerts'
import Landing from './pages/Landing'
import Users from './pages/Users'
import Settings from './pages/Settings'
import ErrorBoundary from './components/ErrorBoundary'
import { ToastProvider } from './components/ToastSystem'
import { fetchAlerts } from './services/api'

const navGroups = [
  {
    title: 'Overview',
    links: [
      { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
      { to: '/heatmap', icon: Thermometer, label: 'Risk Heatmap' },
    ],
  },
  {
    title: 'Investigation',
    links: [
      { to: '/forensics', icon: Fingerprint, label: 'Forensics' },
      { to: '/alerts', icon: AlertTriangle, label: 'Active Alerts' },
    ],
  },
  {
    title: 'System',
    links: [
      { to: '/users', icon: UsersIcon, label: 'Users' },
      { to: '/settings', icon: SettingsIcon, label: 'Settings' },
    ],
  },
]

const pageTitles = {
  '/dashboard': 'Security Operations',
  '/heatmap': 'Risk Heatmap',
  '/forensics': 'Forensics Analysis',
  '/alerts': 'Active Alerts',
  '/users': 'User Directory',
  '/settings': 'System Settings',
}

function App() {
  const location = useLocation()
  const isLanding = location.pathname === '/'
  const pageTitle = pageTitles[location.pathname] || 'Dashboard'

  // Real, honest open-alert count for the header bell (null → no badge).
  const [openAlerts, setOpenAlerts] = useState(null)
  // Mobile sidebar drawer.
  const [navOpen, setNavOpen] = useState(false)

  // Close the mobile drawer on navigation.
  useEffect(() => { setNavOpen(false) }, [location.pathname])

  // Wire the bell to a real count of open alerts; refresh periodically.
  useEffect(() => {
    if (isLanding) return
    let cancelled = false
    const load = async () => {
      const res = await fetchAlerts({ status: 'open', limit: 1 })
      if (cancelled) return
      const count = typeof res?.total === 'number'
        ? res.total
        : Array.isArray(res?.alerts) ? res.alerts.length : null
      setOpenAlerts(count)
    }
    load()
    const id = setInterval(load, 60000)
    return () => { cancelled = true; clearInterval(id) }
  }, [isLanding])

  // Landing renders standalone at "/" — do not wrap in the app shell.
  if (isLanding) {
    return (
      <ErrorBoundary>
        <Landing />
      </ErrorBoundary>
    )
  }

  const SidebarContent = (
    <>
      {/* Logo */}
      <div className="px-5 py-6 flex items-center gap-3">
        <div className="bg-primary/10 rounded-xl p-2">
          <Shield size={22} className="text-primary" aria-hidden="true" />
        </div>
        <div>
          <h1 className="text-base font-bold text-on-surface tracking-tight">UBA ITD</h1>
          <p className="text-[0.65rem] text-on-surface-muted font-mono uppercase tracking-widest">
            Vigilant Lens
          </p>
        </div>
        {/* Close button (mobile only) */}
        <button
          type="button"
          onClick={() => setNavOpen(false)}
          className="icon-btn ml-auto lg:hidden"
          aria-label="Close navigation"
        >
          <X size={18} aria-hidden="true" />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 space-y-6 overflow-y-auto" aria-label="Primary">
        {navGroups.map((group) => (
          <div key={group.title}>
            <p className="px-3 mb-2 text-[0.65rem] font-mono font-semibold text-on-surface-muted uppercase tracking-widest">
              {group.title}
            </p>
            <div className="space-y-0.5">
              {group.links.map(({ to, icon: Icon, label }) => (
                <NavLink
                  key={to}
                  to={to}
                  end
                  className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                >
                  <Icon size={18} aria-hidden="true" />
                  <span className="flex-1">{label}</span>
                  {to === '/alerts' && openAlerts > 0 && (
                    <span
                      className="badge badge-critical !px-1.5 !py-0 min-w-[1.25rem] justify-center"
                      aria-label={`${openAlerts} open alerts`}
                    >
                      {openAlerts > 99 ? '99+' : openAlerts}
                    </span>
                  )}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* Sidebar Footer — neutral / honest */}
      <div className="px-5 py-4 border-t border-surface-variant">
        <p className="text-xs font-medium text-on-surface-variant">Security Analyst</p>
        <p className="text-[0.65rem] text-on-surface-muted font-mono">UBA ITD Console</p>
      </div>
    </>
  )

  return (
    <div className="flex h-screen overflow-hidden bg-surface-base">
      {/* ─── Sidebar (desktop) ─── */}
      <aside className="hidden lg:flex w-64 flex-shrink-0 bg-surface-lowest flex-col border-r border-surface-variant">
        {SidebarContent}
      </aside>

      {/* ─── Sidebar (mobile drawer) ─── */}
      {navOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setNavOpen(false)}
            aria-hidden="true"
          />
          <aside className="absolute inset-y-0 left-0 w-64 bg-surface-lowest flex flex-col border-r border-surface-variant animate-slide-up">
            {SidebarContent}
          </aside>
        </div>
      )}

      {/* ─── Main Area ─── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Header */}
        <header className="h-16 flex-shrink-0 bg-surface-low/70 backdrop-blur-md flex items-center justify-between gap-3 px-4 sm:px-6 lg:px-8 border-b border-surface-variant">
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              onClick={() => setNavOpen(true)}
              className="icon-btn lg:hidden"
              aria-label="Open navigation"
            >
              <Menu size={20} aria-hidden="true" />
            </button>
            <h2 className="text-base sm:text-lg font-semibold text-on-surface truncate">{pageTitle}</h2>
          </div>
          <div className="flex items-center gap-3 sm:gap-4">
            <div className="hidden sm:flex items-center gap-2 bg-success-dim/20 text-success px-3 py-1.5 rounded-full text-xs font-mono font-medium">
              <span className="live-dot" aria-hidden="true" />
              LIVE
            </div>
            <NavLink
              to="/alerts"
              className="icon-btn relative"
              aria-label={openAlerts > 0 ? `Alerts, ${openAlerts} open` : 'Alerts'}
            >
              <Bell size={18} aria-hidden="true" />
              {openAlerts > 0 && (
                <span
                  className="absolute -top-0.5 -right-0.5 min-w-[1rem] h-4 px-1 bg-error-container text-[0.6rem] font-bold text-error rounded-full flex items-center justify-center"
                  aria-hidden="true"
                >
                  {openAlerts > 99 ? '99+' : openAlerts}
                </span>
              )}
            </NavLink>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto overflow-x-hidden p-4 sm:p-6 lg:p-8 bg-surface-low">
          <ErrorBoundary>
            <Routes>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/heatmap" element={<RiskHeatmap />} />
              <Route path="/forensics" element={<Forensics />} />
              <Route path="/alerts" element={<Alerts />} />
              <Route path="/users" element={<Users />} />
              <Route path="/settings" element={<Settings />} />
              {/* Catch-all → dashboard so unknown paths never render a blank area. */}
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </ErrorBoundary>
        </main>
      </div>
    </div>
  )
}

export default function AppWithProviders() {
  return (
    <ToastProvider>
      <App />
    </ToastProvider>
  )
}
