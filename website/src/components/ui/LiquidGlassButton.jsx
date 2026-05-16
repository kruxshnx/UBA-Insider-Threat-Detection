import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva } from 'class-variance-authority'
import { cn } from '../../lib/utils'

/* ─── SVG Glass Filter ─── */
function GlassFilter() {
  return (
    <svg className="hidden">
      <defs>
        <filter
          id="container-glass"
          x="0%" y="0%" width="100%" height="100%"
          colorInterpolationFilters="sRGB"
        >
          <feTurbulence type="fractalNoise" baseFrequency="0.05 0.05" numOctaves="1" seed="1" result="turbulence" />
          <feGaussianBlur in="turbulence" stdDeviation="2" result="blurredNoise" />
          <feDisplacementMap in="SourceGraphic" in2="blurredNoise" scale="70" xChannelSelector="R" yChannelSelector="B" result="displaced" />
          <feGaussianBlur in="displaced" stdDeviation="4" result="finalBlur" />
          <feComposite in="finalBlur" in2="finalBlur" operator="over" />
        </filter>
      </defs>
    </svg>
  )
}

/* ─── Liquid Glass Button Variants ─── */
const liquidVariants = cva(
  'inline-flex items-center justify-center cursor-pointer gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all duration-300 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 outline-none',
  {
    variants: {
      variant: {
        default: 'text-primary hover:scale-105',
        ghost: 'text-on-surface-variant hover:text-on-surface hover:scale-105',
        danger: 'text-error hover:scale-105',
      },
      size: {
        xs: 'h-7 px-2.5 text-xs gap-1',
        sm: 'h-8 px-3 text-xs gap-1.5',
        default: 'h-9 px-4 py-2 gap-2',
        lg: 'h-10 px-6 gap-2',
        xl: 'h-12 px-8 text-base gap-2.5',
        xxl: 'h-14 px-10 text-lg gap-3',
        icon: 'h-9 w-9 p-0',
        'icon-sm': 'h-7 w-7 p-0',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
)

/* ─── Main Liquid Glass Button ─── */
export function LiquidButton({ className, variant, size, asChild = false, children, ...props }) {
  const Comp = asChild ? Slot : 'button'

  return (
    <Comp
      data-slot="button"
      className={cn('relative', liquidVariants({ variant, size, className }))}
      {...props}
    >
      {/* Glass shell */}
      <div className="absolute top-0 left-0 z-0 h-full w-full rounded-full shadow-[0_0_8px_rgba(0,0,0,0.03),0_2px_6px_rgba(0,0,0,0.08),inset_3px_3px_0.5px_-3.5px_rgba(255,255,255,0.09),inset_-3px_-3px_0.5px_-3.5px_rgba(255,255,255,0.85),inset_1px_1px_1px_-0.5px_rgba(255,255,255,0.6),inset_-1px_-1px_1px_-0.5px_rgba(255,255,255,0.6),inset_0_0_6px_6px_rgba(255,255,255,0.12),inset_0_0_2px_2px_rgba(255,255,255,0.06),0_0_12px_rgba(0,0,0,0.15)] transition-all" />
      {/* Backdrop distortion */}
      <div
        className="absolute top-0 left-0 isolate -z-10 h-full w-full overflow-hidden rounded-md"
        style={{ backdropFilter: 'url("#container-glass")' }}
      />
      {/* Content */}
      <div className="pointer-events-none z-10">
        {children}
      </div>
      <GlassFilter />
    </Comp>
  )
}

/* ─── Gradient Primary Button (with liquid glass shine) ─── */
export function GlassPrimaryButton({ className, children, ...props }) {
  return (
    <button
      className={cn(
        'relative inline-flex items-center justify-center gap-2 cursor-pointer',
        'bg-gradient-to-r from-primary to-primary-container text-on-primary',
        'font-semibold rounded-xl overflow-hidden',
        'transition-all duration-300',
        'hover:shadow-[0_4px_24px_rgba(6,182,212,0.4)] hover:scale-[1.03]',
        'active:scale-[0.97] active:shadow-none',
        'disabled:pointer-events-none disabled:opacity-50',
        className
      )}
      {...props}
    >
      {/* Liquid glass overlay */}
      <div className="absolute inset-0 rounded-xl shadow-[inset_1px_1px_2px_rgba(255,255,255,0.3),inset_-1px_-1px_2px_rgba(0,0,0,0.1)] pointer-events-none" />
      {/* Shine sweep on hover */}
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent translate-x-[-100%] hover:translate-x-[100%] transition-transform duration-700 pointer-events-none" />
      <span className="relative z-10 flex items-center gap-2">{children}</span>
    </button>
  )
}

/* ─── Ghost / Outline Glass Button ─── */
export function GlassGhostButton({ className, children, ...props }) {
  return (
    <button
      className={cn(
        'relative inline-flex items-center justify-center gap-2 cursor-pointer',
        'bg-transparent text-on-surface-variant',
        'border border-outline-variant/20 rounded-xl overflow-hidden',
        'font-medium text-sm',
        'transition-all duration-300',
        'hover:bg-surface-highest/40 hover:text-on-surface hover:border-primary/30',
        'hover:shadow-[0_0_12px_rgba(6,182,212,0.1),inset_0_0_8px_rgba(255,255,255,0.05)]',
        'hover:scale-[1.02]',
        'active:scale-[0.97]',
        'disabled:pointer-events-none disabled:opacity-50',
        className
      )}
      {...props}
    >
      <div className="absolute inset-0 rounded-xl shadow-[inset_1px_1px_1px_rgba(255,255,255,0.05),inset_-1px_-1px_1px_rgba(0,0,0,0.05)] pointer-events-none" />
      <span className="relative z-10 flex items-center gap-2">{children}</span>
    </button>
  )
}

/* ─── Icon Glass Button ─── */
export function GlassIconButton({ className, children, ...props }) {
  return (
    <button
      className={cn(
        'relative inline-flex items-center justify-center cursor-pointer',
        'w-9 h-9 rounded-lg overflow-hidden',
        'bg-transparent text-on-surface-variant',
        'transition-all duration-300',
        'hover:bg-surface-highest/40 hover:text-on-surface',
        'hover:shadow-[0_0_10px_rgba(6,182,212,0.08),inset_0_0_6px_rgba(255,255,255,0.05)]',
        'hover:scale-110',
        'active:scale-95',
        className
      )}
      {...props}
    >
      <div className="absolute inset-0 rounded-lg shadow-[inset_1px_1px_1px_rgba(255,255,255,0.04)] pointer-events-none" />
      <span className="relative z-10">{children}</span>
    </button>
  )
}

/* ─── Danger Glass Button ─── */
export function GlassDangerButton({ className, children, ...props }) {
  return (
    <button
      className={cn(
        'relative inline-flex items-center justify-center gap-2 cursor-pointer',
        'bg-error-container/20 text-error border border-error-container/30',
        'font-medium text-sm rounded-xl overflow-hidden',
        'transition-all duration-300',
        'hover:bg-error-container/30 hover:shadow-[0_0_16px_rgba(147,0,10,0.2)]',
        'hover:scale-[1.02]',
        'active:scale-[0.97]',
        className
      )}
      {...props}
    >
      <div className="absolute inset-0 rounded-xl shadow-[inset_1px_1px_1px_rgba(255,180,171,0.1)] pointer-events-none" />
      <span className="relative z-10 flex items-center gap-2">{children}</span>
    </button>
  )
}
