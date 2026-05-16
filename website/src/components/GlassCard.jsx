export default function GlassCard({ children, className = '', hover = true, ...props }) {
  return (
    <div
      className={`glass-card p-6 ${hover ? '' : 'hover:border-transparent hover:shadow-none'} ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}
