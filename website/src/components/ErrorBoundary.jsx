import { Component } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('[ErrorBoundary]', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex items-center justify-center h-96">
          <div className="glass-card p-8 text-center max-w-md">
            <div className="bg-error-container/30 rounded-xl p-3 inline-flex mb-4">
              <AlertTriangle size={28} className="text-error" />
            </div>
            <h2 className="text-lg font-semibold text-on-surface mb-2">Something went wrong</h2>
            <p className="text-xs text-on-surface-variant mb-4 font-mono">
              {this.state.error?.message || 'An unexpected error occurred'}
            </p>
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              className="btn-primary text-sm flex items-center gap-2 mx-auto"
            >
              <RefreshCw size={14} /> Try Again
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

export default ErrorBoundary
