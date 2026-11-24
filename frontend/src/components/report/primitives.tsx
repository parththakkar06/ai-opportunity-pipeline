import { m, type Variants } from 'framer-motion'
import { createContext, useContext, type ReactNode } from 'react'
import { duration, ease, staggerOnce } from '../../lib/motion'
import type { ChallengeCategory, Level } from '../../types'
import { AlertIcon, Badge, Card, GearIcon, TrendIcon, UsersIcon, cx, type Tone } from '../ui'

// ---------------------------------------------------------------------------------------------- entrance
// The report gets one entrance (a 40ms stagger) the first time it opens. Tab switches use a plain fade.
const RevealContext = createContext(false)

const item: Variants = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0, transition: { duration: duration.base, ease: ease.out } },
}

export function RevealGroup({ enabled, className, children }: { enabled: boolean; className?: string; children: ReactNode }) {
  if (!enabled) return <div className={className}>{children}</div>
  return (
    <RevealContext.Provider value>
      <m.div className={className} variants={staggerOnce} initial="initial" animate="animate">
        {children}
      </m.div>
    </RevealContext.Provider>
  )
}

export function Reveal({ className, children, id }: { className?: string; children: ReactNode; id?: string }) {
  const on = useContext(RevealContext)
  if (!on)
    return (
      <div className={className} id={id}>
        {children}
      </div>
    )
  return (
    <m.div className={className} variants={item} id={id}>
      {children}
    </m.div>
  )
}

// ---------------------------------------------------------------------------------------------- layout
export function Section({
  title,
  description,
  action,
  className,
  children,
}: {
  title: string
  description?: ReactNode
  action?: ReactNode
  className?: string
  children: ReactNode
}) {
  return (
    <Reveal>
      <Card className={cx('p-5 sm:p-6', className)}>
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-lg font-semibold text-foreground">{title}</h2>
            {description && <p className="mt-0.5 text-sm text-muted-foreground">{description}</p>}
          </div>
          {action}
        </div>
        {children}
      </Card>
    </Reveal>
  )
}

export function EmptyNote({ children }: { children: ReactNode }) {
  return <p className="text-base text-muted-foreground">{children}</p>
}

export function Chips({ items, tone = 'slate', empty }: { items: string[]; tone?: 'slate' | 'accent'; empty: string }) {
  if (items.length === 0) return <EmptyNote>{empty}</EmptyNote>
  return (
    <ul className="flex flex-wrap gap-2">
      {items.map((label) => (
        <li key={label}>
          <span
            className={cx(
              'inline-flex items-center rounded-full px-3 py-1 text-sm font-medium ring-1 ring-inset',
              tone === 'slate' ? 'bg-subtle text-secondary ring-border' : 'bg-accent-soft text-accent-soft-foreground ring-accent/20',
            )}
          >
            {label}
          </span>
        </li>
      ))}
    </ul>
  )
}

export function ExternalLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a
      href={href.startsWith('http') ? href : `https://${href}`}
      target="_blank"
      rel="noreferrer noopener"
      className="font-medium text-accent underline-offset-2 hover:underline"
    >
      {children}
      <span className="sr-only"> (opens in a new tab)</span>
    </a>
  )
}

// ---------------------------------------------------------------------------------------------- labels
export const CATEGORY: Record<ChallengeCategory, { label: string; icon: ReactNode }> = {
  operational: { label: 'Operational', icon: <GearIcon className="h-4 w-4" /> },
  sales: { label: 'Sales', icon: <TrendIcon className="h-4 w-4" /> },
  customer_experience: { label: 'Customer experience', icon: <UsersIcon className="h-4 w-4" /> },
}

const SEVERITY_TONE: Record<Level, Tone> = { high: 'red', medium: 'amber', low: 'slate' }

/** Severity is always icon + word, never color alone. */
export function SeverityBadge({ level }: { level: Level }) {
  return (
    <Badge tone={SEVERITY_TONE[level]}>
      <AlertIcon className="h-3 w-3" />
      {level[0].toUpperCase() + level.slice(1)} severity
    </Badge>
  )
}

export function ConfidenceBadge({ level }: { level: Level }) {
  const dots = level === 'high' ? 3 : level === 'medium' ? 2 : 1
  return (
    <Badge>
      <span className="flex gap-0.5" aria-hidden="true">
        {[1, 2, 3].map((d) => (
          <span key={d} className={cx('h-1.5 w-1.5 rounded-full', d <= dots ? 'bg-secondary' : 'bg-border-strong')} />
        ))}
      </span>
      {level[0].toUpperCase() + level.slice(1)} confidence
    </Badge>
  )
}

export function StatCard({ label, value, hint }: { label: string; value: string | null; hint?: string }) {
  return (
    <div className="flex min-h-28 flex-col justify-between rounded-xl border border-border bg-subtle p-4">
      <p className="text-sm font-medium text-muted-foreground">{label}</p>
      {value ? (
        <p className="mt-2 text-lg leading-snug font-semibold text-balance text-foreground">{value}</p>
      ) : (
        <p className="mt-2 text-base text-muted-foreground">{hint ?? 'Not public'}</p>
      )}
    </div>
  )
}
