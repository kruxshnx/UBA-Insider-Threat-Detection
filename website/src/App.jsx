import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import {
  Shield,
  LayoutDashboard,
  Thermometer,
  Fingerprint,
  AlertTriangle,
  Users as UsersIcon,
  Settings as SettingsIcon,
  Bell,
} from 'lucide-react'

import Dashboard from './pages/Dashboard'
import RiskHeatmap from './pages/RiskHeatmap'
import Forensics from './pages/Forensics'
import Alerts from './pages/Alerts'
import Landing from './pages/Landing'
import Users from './pages/Users'
import Settings from './pages/Settings'
import ErrorBoundary from './components/ErrorBoundary'
import { GlassIconButton } from './components/ui/LiquidGlassButton'

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
  '/users': 'User Leaderboard',
  '/settings': 'System Settings',
}

function App() {
  const location = useLocation()
  const isLanding = location.pathname === '/'
  const pageTitle = pageTitles[location.pathname] || 'Dashboard'

  if (isLanding) {
    return (
      <ErrorBoundary>
        <Landing />
      </ErrorBoundary>
    )
  }

  return (
    <div className="flex h-screen overflow-hidden">
      {/* ─── Sidebar ─── */}
      <aside className="w-64 flex-shrink-0 bg-surface-lowest flex flex-col border-r border-outline-variant/10">
        {/* Logo */}
        <div className="px-5 py-6 flex items-center gap-3">
          <div className="bg-primary/10 rounded-xl p-2">
            <Shield size={22} className="text-primary" />
          </div>
          <div>
            <h1 className="text-base font-bold text-on-surface tracking-tight">UBA ITD</h1>
            <p className="text-[0.65rem] text-text-muted font-mono uppercase tracking-widest">Vigilant Lens</p>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 space-y-6 overflow-y-auto">
          {navGroups.map((group) => (
            <div key={group.title}>
              <p className="px-3 mb-2 text-[0.65rem] font-mono font-semibold text-text-muted uppercase tracking-widest">
                {group.title}
              </p>
              <div className="space-y-0.5">
                {group.links.map(({ to, icon: Icon, label }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end
                    className={({ isActive }) =>
                      `nav-link ${isActive ? 'active' : ''}`
                    }
                  >
                    <Icon size={18} />
                    {label}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* Sidebar Footer */}
        <div className="px-5 py-4 border-t border-outline-variant/10">
          <p className="text-xs font-medium text-on-surface-variant">SOC Analyst</p>
          <p className="text-[0.65rem] text-text-muted font-mono">Level 3 Access</p>
        </div>
      </aside>

      {/* ─── Main Area ─── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Header */}
        <header className="h-16 flex-shrink-0 bg-surface-low/50 backdrop-blur-sm flex items-center justify-between px-8 border-b border-outline-variant/10">
          <h2 className="text-lg font-semibold text-on-surface">{pageTitle}</h2>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 bg-success-dim/20 text-success px-3 py-1.5 rounded-full text-xs font-mono font-medium">
              <span className="live-dot" />
              LIVE
            </div>
            <GlassIconButton className="relative">
              <Bell size={18} />
              <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-error-container text-[0.6rem] font-bold text-error rounded-full flex items-center justify-center z-20">
                3
              </span>
            </GlassIconButton>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto p-8 bg-surface-low">
          <ErrorBoundary>
            <Routes>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/heatmap" element={<RiskHeatmap />} />
              <Route path="/forensics" element={<Forensics />} />
              <Route path="/alerts" element={<Alerts />} />
              <Route path="/users" element={<Users />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </ErrorBoundary>
        </main>
      </div>
    </div>
  )
}

export default App
