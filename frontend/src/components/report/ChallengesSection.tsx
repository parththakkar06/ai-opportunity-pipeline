import { AnimatePresence, m } from 'framer-motion'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { duration, ease } from '../../lib/motion'
import { Cite } from './Citations'
import type { AssessmentReport, BusinessChallenge, ChallengeCategory } from '../../types'
import { Card, cx } from '../ui'
import { CATEGORY, ConfidenceBadge, RevealGroup, Reveal, SeverityBadge } from './primitives'

type Filter = 'all' | ChallengeCategory
const ORDER: ChallengeCategory[] = ['operational', 'sales', 'customer_experience']
const URL_KEY = 'cat'

/** The category filter lives in the URL (?cat=sales) so a filtered view can be shared. */
function readFilter(): Filter {
  const v = new URLSearchParams(window.location.search).get(URL_KEY)
  return v && (ORDER as string[]).includes(v) ? (v as ChallengeCategory) : 'all'
}

function writeFilter(filter: Filter) {
  const url = new URL(window.location.href)
  if (filter !== 'all') url.searchParams.set(URL_KEY, filter)
  else url.searchParams.delete(URL_KEY)
  if (url.href !== window.location.href) window.history.replaceState(window.history.state, '', url)
}

export const challengeAnchor = (id: string) => `challenge-${id}`

export function ChallengesSection({
  report,
  entrance,
  highlightId,
}: {
  report: AssessmentReport
  entrance: boolean
  highlightId?: string | null
}) {
  const [filter, setFilterState] = useState<Filter>(readFilter)
  const setFilter = (next: Filter) => {
    setFilterState(next)
    writeFilter(next)
  }
  // (useUrlState drops ?cat= when you switch tab or report, so no cleanup is needed here.)
  const all = report.business_challenges
  const counts = useMemo(
    () => Object.fromEntries(ORDER.map((c) => [c, all.filter((x) => x.category === c).length])) as Record<ChallengeCategory, number>,
    [all],
  )
  const visible = filter === 'all' ? all : all.filter((c) => c.category === filter)
  const highSeverity = all.filter((c) => c.severity === 'high').length
  const legacy = !report.stages_completed.includes(2)

  // Jumped here from an opportunity's "Solves" chip: show it even if a filter hides it, then focus it.
  useEffect(() => {
    if (!highlightId) return
    setFilterState('all')
    writeFilter('all')
    const t = window.setTimeout(() => {
      const el = document.getElementById(challengeAnchor(highlightId))
      el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      el?.focus({ preventScroll: true })
    }, 80)
    return () => window.clearTimeout(t)
  }, [highlightId])

  return (
    <RevealGroup enabled={entrance} className="space-y-5">
      <Reveal>
        <Card className="p-5 sm:p-6">
          <p className="max-w-prose text-base text-secondary">
            <span className="font-semibold text-foreground">{all.length} challenges</span> diagnosed from public signals
            {highSeverity > 0 && (
              <>
                , <span className="font-semibold text-foreground">{highSeverity} high severity</span>
              </>
            )}
            . Each one states the <span className="font-semibold text-foreground">reasoning</span> that links the evidence to
            the conclusion.
          </p>
          {legacy && (
            <p className="mt-3 rounded-lg bg-warning-soft p-3 text-sm text-warning-foreground ring-1 ring-warning/30">
              The challenge-analysis stage hasn’t run for this saved report, so these come from the researcher’s bottleneck notes.
              Resume the run to get full reasoning.
            </p>
          )}
          <div className="no-print mt-4 flex flex-wrap gap-2" role="group" aria-label="Filter challenges by category">
            <FilterButton active={filter === 'all'} onClick={() => setFilter('all')} label="All" count={all.length} />
            {ORDER.filter((c) => counts[c] > 0).map((c) => (
              <FilterButton
                key={c}
                active={filter === c}
                onClick={() => setFilter(c)}
                label={CATEGORY[c].label}
                count={counts[c]}
                icon={CATEGORY[c].icon}
              />
            ))}
          </div>
        </Card>
      </Reveal>

      <p className="sr-only" aria-live="polite">
        Showing {visible.length} of {all.length} challenges.
      </p>

      <ol className="space-y-4">
        <AnimatePresence initial={false} mode="popLayout">
          {visible.map((c) => (
            <m.li
              key={c.id}
              layout="position"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1, transition: { duration: duration.base, ease: ease.out } }}
              exit={{ opacity: 0, transition: { duration: duration.fast, ease: ease.in } }}
            >
              <ChallengeCard c={c} highlighted={c.id === highlightId} />
            </m.li>
          ))}
        </AnimatePresence>
      </ol>
    </RevealGroup>
  )
}

function FilterButton({
  active,
  onClick,
  label,
  count,
  icon,
}: {
  active: boolean
  onClick: () => void
  label: string
  count: number
  icon?: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cx(
        'inline-flex min-h-11 items-center gap-2 rounded-full px-4 text-sm font-semibold ring-1 ring-inset transition-colors duration-150',
        active ? 'bg-primary text-on-primary ring-primary' : 'bg-card text-secondary ring-border-strong hover:bg-subtle',
      )}
    >
      {icon}
      {label}
      <span className={cx('tabular-nums', active ? 'opacity-80' : 'text-muted-foreground')}>{count}</span>
    </button>
  )
}

function ChallengeCard({ c, highlighted }: { c: BusinessChallenge; highlighted: boolean }) {
  return (
    <article
      id={challengeAnchor(c.id)}
      tabIndex={-1}
      aria-labelledby={`${challengeAnchor(c.id)}-title`}
      className={cx(
        '@container scroll-mt-40 rounded-2xl border bg-card p-5 shadow-sm transition-shadow duration-300 sm:p-6',
        highlighted ? 'border-accent ring-4 ring-accent/25' : 'border-border',
      )}
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            {CATEGORY[c.category].icon}
            {CATEGORY[c.category].label}
            <span className="font-mono text-xs">· {c.id}</span>
          </p>
          <h2 id={`${challengeAnchor(c.id)}-title`} className="mt-1 text-xl font-semibold text-foreground">
            {c.title}
            <Cite id={c.id} />
          </h2>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <SeverityBadge level={c.severity} />
          <ConfidenceBadge level={c.confidence} />
        </div>
      </header>

      <p className="mt-3 max-w-prose text-base text-secondary">{c.description}</p>

      <div className="mt-5 rounded-xl border-l-4 border-accent bg-accent-soft p-4 sm:p-5">
        <h3 className="text-xs font-bold tracking-widest text-accent-soft-foreground uppercase">Reasoning</h3>
        <p className="mt-2 max-w-prose text-base leading-relaxed text-foreground">{c.reasoning}</p>
      </div>

      <div className="mt-5 grid gap-5 @xl:grid-cols-2">
        <div>
          <h3 className="text-sm font-semibold text-muted-foreground">Research signals</h3>
          <ul className="mt-2 space-y-1.5">
            {c.signals.map((s) => (
              <li key={s} className="flex gap-2 text-base text-secondary">
                <span className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-border-strong" aria-hidden="true" />
                {s}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="text-sm font-semibold text-muted-foreground">Business impact</h3>
          <p className="mt-2 text-base text-secondary">{c.business_impact}</p>
        </div>
      </div>
    </article>
  )
}
