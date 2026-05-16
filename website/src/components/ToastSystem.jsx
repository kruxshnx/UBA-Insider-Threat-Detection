import { useState, useEffect, createContext, useContext, useCallback } from 'react'
import { CheckCircle, AlertTriangle, Info, X } from 'lucide-react'

const ToastContext = createContext(null)
export const useToast = () => useContext(ToastContext)

const iconMap = {
  success: CheckCircle,
  warning: AlertTriangle,
  info: Info,
  error: AlertTriangle,
}

const colorMap = {
  success: 'text-success border-success/30',
  warning: 'text-tertiary border-tertiary/30',
  info: 'text-primary border-primary/30',
  error: 'text-error border-error/30',
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const addToast = useCallback((message, type = 'info', duration = 4000) => {
    const id = Date.now()
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), duration)
  }, [])

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      <div className="fixed bottom-6 right-6 z-50 space-y-2 max-w-sm">
        {toasts.map(toast => {
          const Icon = iconMap[toast.type] || Info
          return (
            <div
              key={toast.id}
              className={`glass-card flex items-center gap-3 px-4 py-3 border-l-2 animate-slide-up ${colorMap[toast.type] || colorMap.info}`}
            >
              <Icon size={16} />
              <span className="text-xs text-on-surface flex-1">{toast.message}</span>
              <button onClick={() => removeToast(toast.id)} className="text-text-muted hover:text-on-surface">
                <X size={12} />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export default function ToastSystem() {
  return null
}
