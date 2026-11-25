import { ChevronRight } from 'lucide-react'
import { Fragment, useId, useState } from 'react'

import { cn } from '@/lib/utils'
import type { AssessmentReport, ReportOpportunity } from '@/types'

import { Cite } from './Citations'

const COLUMNS = [
  { key: 'roi_potential', short: 'ROI', label: 'ROI potential (adjusted for evidence)' },
  { key: 'ceo_relevance', short: 'CEO', label: 'Relevance to CEO priorities' },
  { key: 'feasibility', short: 'Feas.', label: 'Feasibility' },
  { key: 'speed_to_value', short: 'Speed', label: 'Speed to value' },
  { key: 'competitive_moat', short: 'Moat', label: 'Competitive moat' },
] as const

const READINESS = { have: 'Have', likely: 'Likely', missing: 'Missing' } as const

function score(o: ReportOpportunity, key: string): number | null {
  if (key === 'roi_potential' && o.roi_adjusted != null) return o.roi_adjusted
  return o.rubric.find((r) => r.criterion === key)?.score ?? null
}

function Bar({ value }: { value: number | null }) {
  if (value == null) return <span className="text-ink-3">—</span>
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="num w-7 text-right">{Number.isInteger(value) ? value : value.toFixed(1)}</span>
      <span aria-hidden="true" className="hidden h-1 w-6 bg-tint lg:block">
        <span className="block h-full bg-ink-3" style={{ width: `${value * 10}%` }} />
      </span>
    </span>
  )
}

/** A compact ranking table; each row expands in place to the full plan for that idea. */
export function Opportunities({ report: r }: { report: AssessmentReport }) {
  const [open, setOpen] = useState<string | null>(r.recommended_opportunity_id)
  const baseId = useId()
  const opps = r.ai_opportunities
  if (!opps.length) return <p className="meta">The AI opportunity stage hasn't run for this company yet.</p>
  const toggle = (id: string) => setOpen((v) => (v === id ? null : id))
  const titleOf = (id: string) => opps.find((o) => o.id === id)?.title ?? id
  const challengeTitle = (id: string) => r.business_challenges.find((c) => c.id === id)?.title ?? id

  return (
    <div>
      <p className="prose-serif text-ink-2">
        Ranked by a weighted rubric computed in Python. ROI is discounted when the value estimate rests on assumptions
        rather than sourced figures. Select an idea to see its pilot plan.
      </p>

      {/* Table (tablet and up) */}
      <div className="mt-6 hidden overflow-x-auto md:block">
        <table className="w-full min-w-[46rem] text-sm">
          <caption className="sr-only">AI opportunities, ranked</caption>
          <thead>
            <tr className="border-b border-rule-strong text-left text-ink-3">
              <th scope="col" className="w-8 py-2 font-normal">#</th>
              <th scope="col" className="py-2 font-normal">Opportunity</th>
              {COLUMNS.map((c) => (
                <th key={c.key} scope="col" className="py-2 pl-2 text-right font-normal" title={c.label}>
                  <abbr title={c.label} className="no-underline">
                    {c.short}
                  </abbr>
                </th>
              ))}
              <th scope="col" className="py-2 pl-3 text-right font-normal" title="Share of the value estimate backed by sourced figures">
                Evidence
              </th>
              <th scope="col" className="py-2 pl-3 text-right font-normal">Score</th>
            </tr>
          </thead>
          <tbody>
            {opps.map((o) => {
              const isOpen = open === o.id
              const panel = `${baseId}-${o.id}`
              return (
                <Fragment key={o.id}>
                  <tr
                    onClick={() => toggle(o.id)}
                    className={cn('cursor-pointer border-b border-rule align-top hover:bg-tint/60', isOpen && 'bg-tint')}
                  >
                    <td className="num py-3 text-ink-3">{o.rank ?? '–'}</td>
                    <th scope="row" className="py-3 pr-3 text-left font-normal">
                      <div className="flex items-start gap-1.5">
                        <button
                          type="button"
                          aria-expanded={isOpen}
                          aria-controls={panel}
                          onClick={(e) => {
                            e.stopPropagation()
                            toggle(o.id)
                          }}
                          className="flex items-start gap-1.5 text-left font-medium text-ink"
                        >
                          <ChevronRight
                            className={cn('mt-0.5 size-4 shrink-0 text-ink-3 transition-transform duration-150', isOpen && 'rotate-90')}
                            strokeWidth={1.5}
                            aria-hidden="true"
                          />
                          {o.title}
                        </button>
                        <span onClick={(e) => e.stopPropagation()}>
                          <Cite id={o.id} />
                        </span>
                      </div>
                      {o.is_recommended && <span className="mt-0.5 ml-[1.375rem] block text-[13px] font-medium text-brand">Recommended</span>}
                      {!o.is_recommended && o.why_not && (
                        <span className="mt-0.5 ml-[1.375rem] block text-[13px] text-ink-3">Why not first: {o.why_not}</span>
                      )}
                    </th>
                    {COLUMNS.map((c) => (
                      <td key={c.key} className="py-3 pl-2 text-right text-ink-2">
                        <Bar value={score(o, c.key)} />
                      </td>
                    ))}
                    <td className="num py-3 pl-3 text-right text-ink-2">
                      {o.evidence_share != null ? `${Math.round(o.evidence_share * 100)}%` : '—'}
                    </td>
                    <td className="num py-3 pl-3 text-right font-semibold text-ink">
                      {o.weighted_score != null ? o.weighted_score.toFixed(0) : '—'}
                    </td>
                  </tr>
                  <tr className={cn(isOpen ? 'border-b border-rule bg-tint' : 'hidden')}>
                    <td />
                    <td colSpan={COLUMNS.length + 3} className="pt-1 pr-4 pb-6">
                      <div id={panel} role="region" aria-label={`${o.title}: details`} inert={!isOpen}>
                        {isOpen && <Detail o={o} challengeTitle={challengeTitle} />}
                      </div>
                    </td>
                  </tr>
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Stacked rows (phones) */}
      <ol className="mt-6 divide-y divide-rule border-y border-rule md:hidden">
        {opps.map((o) => {
          const isOpen = open === o.id
          return (
            <li key={o.id} className="py-3">
              <button
                type="button"
                aria-expanded={isOpen}
                onClick={() => toggle(o.id)}
                className="flex w-full items-start gap-3 text-left [@media(pointer:coarse)]:min-h-11"
              >
                <span className="num w-5 text-ink-3">{o.rank ?? '–'}</span>
                <span className="flex-1">
                  <span className="font-medium text-ink">{o.title}</span>
                  {o.is_recommended && <span className="ml-2 text-[13px] font-medium text-brand">Recommended</span>}
                  <span className="meta num mt-0.5 block">
                    Score {o.weighted_score?.toFixed(0) ?? '—'}
                    {o.evidence_share != null && ` · evidence ${Math.round(o.evidence_share * 100)}%`}
                  </span>
                  {!o.is_recommended && o.why_not && <span className="mt-1 block text-[13px] text-ink-3">Why not first: {o.why_not}</span>}
                </span>
              </button>
              {isOpen && (
                <div className="mt-3 pl-8">
                  <dl className="num mb-4 grid grid-cols-5 gap-2 text-center text-xs">
                    {COLUMNS.map((c) => (
                      <div key={c.key}>
                        <dt className="text-ink-3">{c.short}</dt>
                        <dd className="text-sm text-ink">{score(o, c.key) ?? '—'}</dd>
                      </div>
                    ))}
                  </dl>
                  <Detail o={o} challengeTitle={challengeTitle} />
                </div>
              )}
            </li>
          )
        })}
      </ol>

      {r.sensitivity && (
        <p className="mt-5 max-w-[72ch] text-sm text-ink-2">
          <span className="font-medium text-ink">Sensitivity check:</span>{' '}
          {r.sensitivity.winner_stable
            ? 'the recommended idea still ranks first under conservative assumptions (low value estimates, evidence discount applied twice, harder delivery for high-effort ideas).'
            : `under conservative assumptions, ${titleOf(r.sensitivity.conservative_winner_id)} would rank first instead. Validate the value drivers in the pilot.`}
        </p>
      )}
    </div>
  )
}

function Detail({ o, challengeTitle }: { o: ReportOpportunity; challengeTitle: (id: string) => string }) {
  const pilot = [...(o.pilot_30_60_90 ?? [])].sort((a, b) => a.day - b.day)
  const bvb = o.build_vs_buy
  const block = 'text-sm font-medium text-ink-2'
  return (
    <div className="rise-in grid max-w-[72ch] gap-5 text-[15px] text-ink">
      <div>
        <p className={block}>Problem</p>
        <p className="mt-0.5">{o.problem_solved}</p>
        {o.addresses_challenges.length > 0 && (
          <p className="meta mt-1">
            Solves{' '}
            {o.addresses_challenges.map((id, i) => (
              <span key={id}>
                {i > 0 && ', '}
                <a href={`#challenge-${id}`} className="text-ink-2 underline decoration-rule-strong underline-offset-4 hover:decoration-ink-2">
                  {challengeTitle(id)}
                </a>
              </span>
            ))}
          </p>
        )}
      </div>
      <div>
        <p className={block}>How it works</p>
        <p className="mt-0.5">{o.ai_mechanism}</p>
        <p className="meta mt-1">Applies to: {o.applies_to}</p>
      </div>
      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <p className={block}>Expected impact</p>
          <p className="mt-0.5">{o.expected_impact}</p>
          <p className="meta mt-1">Moves {o.primary_metric}</p>
        </div>
        <div>
          <p className={block}>Effort</p>
          <p className="mt-0.5">{o.effort}</p>
        </div>
      </div>
      {bvb && (
        <div>
          <p className={block}>
            Build vs buy: <span className="font-normal text-ink capitalize">{bvb.decision}</span>
          </p>
          {bvb.vendor_refs.length > 0 && (
            <p className="mt-0.5">
              {bvb.vendor_refs.map((v, i) => (
                <span key={v.name}>
                  {i > 0 && ', '}
                  <a href={v.url} target="_blank" rel="noreferrer noopener" className="text-brand underline decoration-brand/40 underline-offset-4 hover:decoration-brand">
                    {v.name}
                  </a>
                </span>
              ))}
            </p>
          )}
          <p className="mt-0.5 text-ink-2">{bvb.rationale}</p>
        </div>
      )}
      {pilot.length > 0 && (
        <div>
          <p className={block}>30/60/90-day pilot</p>
          <table className="mt-1 w-full text-sm">
            <tbody>
              {pilot.map((m) => (
                <tr key={m.day} className="border-b border-rule align-top last:border-0">
                  <th scope="row" className="num w-16 py-1.5 text-left font-medium text-ink">
                    Day {m.day}
                  </th>
                  <td className="py-1.5 pr-3 text-ink">{m.milestone}</td>
                  <td className="py-1.5 text-ink-2">
                    {m.kpi}: <span className="num">{m.target}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {o.data_readiness && o.data_readiness.length > 0 && (
        <div>
          <p className={block}>Data readiness</p>
          <ul className="mt-1 space-y-0.5 text-sm">
            {o.data_readiness.map((d) => (
              <li key={d.source}>
                <span className="text-ink">{d.source}</span>:{' '}
                <span className={cn('font-medium', d.status === 'missing' ? 'text-caution' : d.status === 'have' ? 'text-positive' : 'text-ink-2')}>
                  {READINESS[d.status]}
                </span>{' '}
                <span className="text-ink-3">({d.reason})</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {o.compliance && o.compliance.length > 0 && (
        <div>
          <p className={block}>Compliance</p>
          <ul className="mt-1 space-y-0.5 text-sm">
            {o.compliance.map((c) => (
              <li key={c.rule_id}>
                <a href={c.url} target="_blank" rel="noreferrer noopener" className="text-brand underline decoration-brand/40 underline-offset-4 hover:decoration-brand">
                  {c.title}
                </a>
                <span className="text-ink-2">: {c.note}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {o.biggest_risk && (
        <p className="text-sm">
          <span className="font-medium text-caution">Biggest risk:</span> <span className="text-ink-2">{o.biggest_risk}</span>
        </p>
      )}
      {o.rubric.length > 0 && (
        <details className="text-sm">
          <summary className="text-ink-2 hover:text-ink">Why these scores</summary>
          <dl className="mt-2 space-y-1.5">
            {o.rubric.map((s) => (
              <div key={s.criterion}>
                <dt className="inline font-medium text-ink">
                  {s.label} <span className="num">{s.score}/10</span>
                </dt>
                <dd className="inline text-ink-2">: {s.rationale}</dd>
              </div>
            ))}
          </dl>
        </details>
      )}
    </div>
  )
}
