import { useState } from 'react'
import { Moon, Sun, Bell, BellOff, Trash2, Download, RefreshCw, CheckCircle, Info } from 'lucide-react'
import GlassCard from '../components/GlassCard'
import { GlassGhostButton } from '../components/ui/LiquidGlassButton'
import { GlowCard } from '../components/ui/spotlight-card'
import { clearCache } from '../services/api'

export default function Settings() {
  const [darkMode, setDarkMode] = useState(true)
  const [thresholds, setThresholds] = useState({ medium: 70, high: 85, critical: 95 })
  const [notifications, setNotifications] = useState({ email: true, browser: false, sound: false })
  const [cacheCleared, setCacheCleared] = useState(false)

  const handleClearCache = async () => {
    await clearCache()
    setCacheCleared(true)
    setTimeout(() => setCacheCleared(false), 3000)
  }

  return (
    <div className="space-y-6 animate-fade-in max-w-4xl">
      {/* Appearance */}
      <GlassCard>
        <h3 className="text-sm font-semibold text-on-surface mb-4">Appearance</h3>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-on-surface">Dark Mode</p>
            <p className="text-xs text-text-muted">Toggle application theme</p>
          </div>
          <button
            onClick={() => setDarkMode(!darkMode)}
            className={`relative w-14 h-7 rounded-full transition-colors ${darkMode ? 'bg-primary/30' : 'bg-surface-highest'}`}
          >
            <span className={`absolute top-0.5 w-6 h-6 rounded-full bg-on-surface flex items-center justify-center transition-transform ${darkMode ? 'translate-x-7' : 'translate-x-0.5'}`}>
              {darkMode ? <Moon size={12} className="text-surface-base" /> : <Sun size={12} className="text-surface-base" />}
            </span>
          </button>
        </div>
      </GlassCard>

      {/* Risk Thresholds */}
      <GlassCard>
        <h3 className="text-sm font-semibold text-on-surface mb-4">Risk Thresholds</h3>
        <div className="space-y-4">
          {Object.entries(thresholds).map(([key, val]) => (
            <div key={key} className="flex items-center justify-between">
              <div>
                <p className="text-sm text-on-surface capitalize">{key} Threshold</p>
                <p className="text-xs text-text-muted">Score ≥ {val} triggers {key} alert</p>
              </div>
              <div className="flex items-center gap-3">
                <input
                  type="range" min={0} max={100} value={val}
                  onChange={e => setThresholds(prev => ({ ...prev, [key]: Number(e.target.value) }))}
                  className="w-32 accent-primary"
                />
                <span className="text-sm font-mono font-bold text-primary w-8 text-right">{val}</span>
              </div>
            </div>
          ))}
        </div>
      </GlassCard>

      {/* Notifications */}
      <GlassCard>
        <h3 className="text-sm font-semibold text-on-surface mb-4">Notifications</h3>
        <div className="space-y-4">
          {Object.entries(notifications).map(([key, enabled]) => (
            <div key={key} className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {enabled ? <Bell size={16} className="text-primary" /> : <BellOff size={16} className="text-text-muted" />}
                <div>
                  <p className="text-sm text-on-surface capitalize">{key} Alerts</p>
                  <p className="text-xs text-text-muted">Receive {key} notifications for new alerts</p>
                </div>
              </div>
              <button
                onClick={() => setNotifications(prev => ({ ...prev, [key]: !prev[key] }))}
                className={`relative w-11 h-6 rounded-full transition-colors ${enabled ? 'bg-primary/30' : 'bg-surface-highest'}`}
              >
                <span className={`absolute top-0.5 w-5 h-5 rounded-full bg-on-surface transition-transform ${enabled ? 'translate-x-5.5' : 'translate-x-0.5'}`} />
              </button>
            </div>
          ))}
        </div>
      </GlassCard>

      {/* Model Configuration */}
      <GlowCard customSize glowColor="purple" className="p-6">
        <h3 className="text-sm font-semibold text-on-surface mb-4">Model Configuration</h3>
        <div className="grid grid-cols-2 gap-3">
          {[
            { label: 'LSTM Sequence Length', value: '10' },
            { label: 'LSTM Hidden Dim', value: '32' },
            { label: 'LSTM Layers', value: '2' },
            { label: 'Training Epochs', value: '10' },
            { label: 'IF Estimators', value: '100' },
            { label: 'IF Contamination', value: '5%' },
          ].map(item => (
            <div key={item.label} className="bg-surface-high rounded-lg p-3">
              <p className="text-xs text-text-muted">{item.label}</p>
              <p className="text-sm font-mono font-bold text-on-surface">{item.value}</p>
            </div>
          ))}
        </div>
      </GlowCard>

      {/* Data Management */}
      <GlassCard>
        <h3 className="text-sm font-semibold text-on-surface mb-4">Data Management</h3>
        <div className="flex gap-3">
          <GlassGhostButton onClick={handleClearCache} className="text-xs px-4 py-2">
            {cacheCleared ? <><CheckCircle size={14} className="text-success" /> Cleared!</> : <><Trash2 size={14} /> Clear Cache</>}
          </GlassGhostButton>
          <GlassGhostButton className="text-xs px-4 py-2">
            <Download size={14} /> Export Report (CSV)
          </GlassGhostButton>
          <GlassGhostButton className="text-xs px-4 py-2">
            <RefreshCw size={14} /> Regenerate Data
          </GlassGhostButton>
        </div>
      </GlassCard>

      {/* About */}
      <GlowCard customSize glowColor="blue" className="p-6">
        <h3 className="text-sm font-semibold text-on-surface mb-4">About</h3>
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Info size={14} className="text-text-muted" />
            <span className="text-xs text-text-muted">Version</span>
            <span className="text-xs font-mono text-on-surface">1.0.0</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-success animate-pulse-glow" />
            <span className="text-xs text-text-muted">API Status</span>
            <span className="text-xs font-mono text-success">Online</span>
          </div>
        </div>
      </GlowCard>
    </div>
  )
}
