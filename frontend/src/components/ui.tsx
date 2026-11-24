import type { ReactNode } from 'react'

export function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ')
}

const TONES = {
  slate: 'bg-muted text-secondary ring-border',
  indigo: 'bg-accent-soft text-accent ring-accent/20',
  green: 'bg-success-soft text-success-foreground ring-success/30',
  amber: 'bg-warning-soft text-warning-foreground ring-warning/30',
  red: 'bg-danger-soft text-danger-foreground ring-danger/30',
  sky: 'bg-accent-soft text-accent-soft-foreground ring-accent/20',
} as const
export type Tone = keyof typeof TONES

export function Badge({ tone = 'slate', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset',
        TONES[tone],
      )}
    >
      {children}
    </span>
  )
}

export function levelTone(level: string): Tone {
  return level === 'high' ? 'red' : level === 'medium' ? 'amber' : 'slate'
}

export function qualityTone(level: string): Tone {
  return level === 'high' ? 'green' : level === 'medium' ? 'amber' : 'red'
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cx('rounded-2xl border border-border bg-card shadow-sm', className)}>{children}</div>
}

export function Label({ children }: { children: ReactNode }) {
  return <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{children}</div>
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="text-sm italic text-muted-foreground">{children}</p>
}

export function Button({
  children,
  onClick,
  variant = 'secondary',
  disabled,
  type = 'button',
  className,
}: {
  children: ReactNode
  onClick?: () => void
  variant?: 'primary' | 'secondary' | 'ghost'
  disabled?: boolean
  type?: 'button' | 'submit'
  className?: string
}) {
  const styles = {
    primary: 'bg-accent text-on-accent shadow-sm hover:bg-accent-hover disabled:bg-accent/50',
    secondary: 'bg-card text-secondary ring-1 ring-inset ring-border-strong hover:bg-subtle disabled:opacity-50',
    ghost: 'text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-50',
  }[variant]
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={cx(
        'inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-colors duration-150 disabled:cursor-not-allowed',
        styles,
        className,
      )}
    >
      {children}
    </button>
  )
}

// Minimal inline icons (stroke = currentColor).
const icon = (d: string) =>
  function Icon({ className = 'h-4 w-4' }: { className?: string }) {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d={d} />
      </svg>
    )
  }

export const CheckIcon = icon('M20 6 9 17l-5-5')
export const CopyIcon = icon('M8 8h12v12H8zM4 16V4h12')
export const DownloadIcon = icon('M12 3v12m0 0 4-4m-4 4-4-4M4 21h16')
export const ExternalIcon = icon('M14 4h6v6m0-6L10 14M19 14v6H4V5h6')
export const SparkIcon = icon('M12 3v4m0 10v4M3 12h4m10 0h4M6 6l2.5 2.5m7 7L18 18M18 6l-2.5 2.5m-7 7L6 18')
export const AlertIcon = icon('M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z')
export const BulbIcon = icon('M9 18h6m-5 3h4M12 3a6 6 0 0 0-3.5 10.9c.6.4 1 1.1 1 1.8V16h5v-.3c0-.7.4-1.4 1-1.8A6 6 0 0 0 12 3z')
export const SearchIcon = icon('M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zm9 3-4.35-4.35')
export const PlusIcon = icon('M12 5v14M5 12h14')
export const CloseIcon = icon('M18 6 6 18M6 6l12 12')
export const ResumeIcon = icon('M5 4v16l13-8z')
export const CircleCheckIcon = icon('M22 11.1V12a10 10 0 1 1-5.9-9.1M22 4 12 14l-3-3')
export const HalfCircleIcon = icon('M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm0 0v20')
export const InfoIcon = icon('M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zm0-14h.01M11 12h1v4h1')
export const MapPinIcon = icon('M12 21s-7-6.2-7-11.5a7 7 0 1 1 14 0C19 14.8 12 21 12 21zm0-9a2 2 0 1 0 0-4 2 2 0 0 0 0 4z')
export const TrendIcon = icon('M3 17l6-6 4 4 8-8M15 7h6v6')
export const GearIcon = icon('M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-2.9-1.2l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.7 1.7 0 0 0 3 15.4H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.2-2.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z')
export const UsersIcon = icon('M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm14 10v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8')
export const ArrowRightIcon = icon('M5 12h14m-6-6 6 6-6 6')
export const FlagIcon = icon('M4 22V4s1-1 4-1 5 2 8 2 4-1 4-1v11s-1 1-4 1-5-2-8-2-4 1-4 1')
export const PrinterIcon = icon('M6 9V2h12v7M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2M6 14h12v8H6z')
export const ShieldIcon = icon('M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z')

export function Spinner({ className = 'h-4 w-4' }: { className?: string }) {
  return (
    <svg className={cx('animate-spin', className)} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.2" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}
