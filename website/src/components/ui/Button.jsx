import { cn } from '../../lib/utils'

/**
 * Button — token-based button matching the .btn utility classes.
 * @param {'primary'|'ghost'|'danger'} [variant='primary']
 * @param {'sm'|'md'} [size='md']
 * @param {React.ComponentType} [icon]   lucide icon rendered before children.
 * @param {string} [as='button']
 *
 * @example <Button variant="ghost" icon={RefreshCw} onClick={reload}>Refresh</Button>
 */
const variants = { primary: 'btn-primary', ghost: 'btn-ghost', danger: 'btn-danger' }
const sizes = { sm: 'text-xs px-3 py-1.5', md: '' }

export function Button({ variant = 'primary', size = 'md', icon: Icon, className = '', children, as: Tag = 'button', ...props }) {
  return (
    <Tag className={cn('btn', variants[variant] || variants.primary, sizes[size], className)} {...props}>
      {Icon && <Icon size={size === 'sm' ? 13 : 15} aria-hidden="true" />}
      {children}
    </Tag>
  )
}

export default Button
