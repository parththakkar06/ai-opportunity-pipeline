import { m } from 'framer-motion'
import type { ReactNode } from 'react'
import { duration, ease } from '../../lib/motion'
import type { AssessmentReport, ReportOpportunity, RubricScore } from '../../types'
import { ArrowRightIcon, Badge, BulbIcon, Card, ShieldIcon, cx } from '../ui'
import { EmptyNote, Reveal, RevealGroup } from './primitives'

export function OpportunitiesSection({
  report,
  entrance,
  onJumpToChallenge,
}: {
  report: AssessmentReport
  entrance: boolean
  onJumpToChallenge: (id: string) => void
}) {
  const opps = report.ai_opportunities
  if (!opps.length)
    return (
      <Card className="p-6">
        <EmptyNote>The AI Opportunity Strategist hasn’t run for this company yet. Resume the run to generate this section.</EmptyNote>
      </Card>
    )
  const titles = Object.fromEntries(report.business_challenges.map((c) => [c.id, c.title]))
  const recommended = opps.find((o) => o.is_recommended) ?? opps[0]
  const others = opps.filter((o) => o.id !== recommended.id)
  const weights = recommended.rubric

  return (
    <RevealGroup enabled={entrance} className="space-y-5">
      <Reveal>
        <p className="max-w-prose text-base text-secondary">
          {opps.length} opportunities, each mapped to the challenges it solves and ranked on a weighted rubric
          {weights.length > 0 && (
            <>
              {' '}(
              {weights.map((w, i) => (
                <span key={w.criterion}>
                  {i > 0 && ', '}
                  {w.label} {Math.round(w.weight * 100)}%
                </span>
              ))}
              )
            </>
          )}
          .
        </p>
      </Reveal>

      <Reveal>
        <article
          className="@container rounded-2xl border-2 border-accent bg-card p-5 shadow-sm sm:p-7"
          aria-labelledby="recommended-title"
        >
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <Badge tone="indigo">
                <BulbIcon className="h-3.5 w-3.5" /> Recommended · rank {recommended.rank ?? 1}
              </Badge>
              <h2 id="recommended-title" className="mt-2 text-2xl font-bold text-foreground">
                {recommended.title}
              </h2>
              <p className="mt-1 text-base text-muted-foreground">{prettyCategory(recommended.category)}</p>
            </div>
            <Score value={recommended.weighted_score} large />
          </div>

          <p className="mt-4 rounded-xl bg-subtle p-4 text-base text-secondary">
            <span className="font-semibold text-foreground">Applies to: </span>
            {recommended.applies_to}
          </p>

          <div className="mt-5 grid gap-6 @2xl:grid-cols-2">
            <div className="space-y-4">
              <Detail level={3} label="Problem solved">{recommended.problem_solved}</Detail>
              <Detail level={3} label="How the AI works">{recommended.ai_mechanism}</Detail>
              <Detail level={3} label="Expected impact">
                {recommended.expected_impact} <span className="text-muted-foreground">· moves {recommended.primary_metric}</span>
              </Detail>
              <Detail level={3} label="Effort">{recommended.effort}</Detail>
              {recommended.evidence_share != null && (
                <p className="text-sm text-muted-foreground">
                  Evidence behind the value estimate: {Math.round(recommended.evidence_share * 100)}% · ROI adjusted to{' '}
                  {recommended.roi_adjusted}/10
                </p>
              )}
              {report.sensitivity && (
                <p className="text-sm text-muted-foreground">
                  Sensitivity check:{' '}
                  {report.sensitivity.winner_stable
                    ? 'still the winner under conservative assumptions.'
                    : `under conservative assumptions, ${
                        opps.find((x) => x.id === report.sensitivity?.conservative_winner_id)?.title ??
                        report.sensitivity.conservative_winner_id
                      } would win instead.`}
                </p>
              )}
            </div>
            <div>
              <h3 className="text-sm font-semibold text-muted-foreground">Rubric scores</h3>
              <RubricBars rubric={recommended.rubric} withRationale />
              {recommended.biggest_risk && (
                <p className="mt-4 flex gap-2 rounded-xl bg-warning-soft p-3 text-sm text-warning-foreground ring-1 ring-warning/30">
                  <ShieldIcon className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>
                    <span className="font-semibold">Biggest risk: </span>
                    {recommended.biggest_risk}
                  </span>
                </p>
              )}
            </div>
          </div>
          <SolvesChips ids={recommended.addresses_challenges} titles={titles} onJump={onJumpToChallenge} />
        </article>
      </Reveal>

      {others.length > 0 && (
        <Reveal>
          <h2 className="pt-2 text-lg font-semibold text-foreground">Also considered</h2>
        </Reveal>
      )}
      <Reveal>
        <ol className="space-y-4">
          {others.map((o) => (
            <li key={o.id}>
              <OpportunityCard o={o} titles={titles} onJump={onJumpToChallenge} />
            </li>
          ))}
        </ol>
      </Reveal>
    </RevealGroup>
  )
}

function OpportunityCard({
  o,
  titles,
  onJump,
}: {
  o: ReportOpportunity
  titles: Record<string, string>
  onJump: (id: string) => void
}) {
  return (
    <article className="@container rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6" aria-labelledby={`opp-${o.id}`}>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-muted-foreground">
            Rank {o.rank ?? '—'} · {prettyCategory(o.category)}
          </p>
          <h3 id={`opp-${o.id}`} className="mt-1 text-xl font-semibold text-foreground">
            {o.title}
          </h3>
        </div>
        <Score value={o.weighted_score} />
      </div>
      <p className="mt-3 text-base text-secondary">
        <span className="font-semibold text-foreground">Applies to: </span>
        {o.applies_to}
      </p>
      <div className="mt-4 grid gap-5 @2xl:grid-cols-2">
        <div className="space-y-3">
          <Detail label="Problem solved">{o.problem_solved}</Detail>
          <Detail label="Expected impact">{o.expected_impact}</Detail>
          {o.evidence_share != null && (
            <p className="text-sm text-muted-foreground">
              Evidence behind the value estimate: {Math.round(o.evidence_share * 100)}% · ROI adjusted to{' '}
              {o.roi_adjusted}/10
            </p>
          )}
          {o.why_not && <p className="text-sm text-muted-foreground italic">Why not: {o.why_not}</p>}
          <details className="group">
            <summary className="inline-flex min-h-11 cursor-pointer items-center text-sm font-semibold text-accent marker:content-none hover:underline">
              <span className="group-open:hidden">Show how it works and effort</span>
              <span className="hidden group-open:inline">Hide details</span>
            </summary>
            <div className="mt-3 space-y-3">
              <Detail label="How the AI works">{o.ai_mechanism}</Detail>
              <Detail label="Effort">{o.effort}</Detail>
              {o.biggest_risk && <Detail label="Biggest risk">{o.biggest_risk}</Detail>}
            </div>
          </details>
        </div>
        <RubricBars rubric={o.rubric} />
      </div>
      <SolvesChips ids={o.addresses_challenges} titles={titles} onJump={onJump} />
    </article>
  )
}

/** Bar + number per criterion; the number is the source of truth, the bar only helps comparison. */
function RubricBars({ rubric, withRationale }: { rubric: RubricScore[]; withRationale?: boolean }) {
  if (!rubric.length) return <p className="mt-2 text-sm text-muted-foreground">Rubric scores not available for this run.</p>
  return (
    <ul className="mt-2 space-y-3" aria-label="Rubric scores">
      {rubric.map((r) => (
        <li key={r.criterion}>
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-sm font-medium text-secondary">
              {r.label} <span className="text-muted-foreground">· {Math.round(r.weight * 100)}% weight</span>
            </span>
            <span className="text-sm font-semibold text-foreground tabular-nums">
              {r.score}
              <span className="font-normal text-muted-foreground">/10</span>
            </span>
          </div>
          <div className="mt-1 h-2 overflow-hidden rounded-full bg-muted" aria-hidden="true">
            <m.div
              className={cx('h-full origin-left rounded-full', r.score >= 7 ? 'bg-accent' : r.score >= 4 ? 'bg-secondary' : 'bg-border-strong')}
              initial={{ scaleX: 0 }}
              animate={{ scaleX: r.score / 10 }}
              transition={{ duration: duration.slow, ease: ease.out }}
            />
          </div>
          {withRationale && <p className="mt-1 text-sm text-muted-foreground">{r.rationale}</p>}
        </li>
      ))}
    </ul>
  )
}

function SolvesChips({ ids, titles, onJump }: { ids: string[]; titles: Record<string, string>; onJump: (id: string) => void }) {
  if (!ids.length) return null
  return (
    <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-border pt-4">
      <span className="text-sm font-semibold text-muted-foreground">Solves</span>
      {ids.map((id) => (
        <button
          key={id}
          type="button"
          onClick={() => onJump(id)}
          className="inline-flex min-h-9 items-center gap-1.5 rounded-full bg-subtle px-3 text-sm font-medium text-secondary ring-1 ring-border ring-inset transition-colors duration-150 hover:bg-accent-soft hover:text-accent-soft-foreground"
        >
          <span className="font-mono text-xs">{id}</span>
          {titles[id] && <span className="max-w-[16rem] truncate">{titles[id]}</span>}
          <ArrowRightIcon className="h-3.5 w-3.5" />
          <span className="sr-only">Go to this challenge</span>
        </button>
      ))}
    </div>
  )
}

function Score({ value, large }: { value: number | null; large?: boolean }) {
  if (value === null) return null
  return (
    <div className="shrink-0 text-right">
      <p className={cx('font-bold text-foreground tabular-nums', large ? 'text-4xl' : 'text-2xl')}>{value.toFixed(0)}</p>
      <p className="text-sm text-muted-foreground">score / 100</p>
    </div>
  )
}

function Detail({ label, children, level = 4 }: { label: string; children: ReactNode; level?: 3 | 4 }) {
  const Heading = level === 3 ? 'h3' : 'h4'
  return (
    <div>
      <Heading className="text-sm font-semibold text-muted-foreground">{label}</Heading>
      <p className="mt-1 text-base text-secondary">{children}</p>
    </div>
  )
}

const prettyCategory = (c: string) => c.replace(/_/g, ' ').replace(/^\w/, (m) => m.toUpperCase())
