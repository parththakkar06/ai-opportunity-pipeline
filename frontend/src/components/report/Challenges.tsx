import { useState } from 'react'

import { cn } from '@/lib/utils'
import type { AssessmentReport, ChallengeCategory } from '@/types'

import { Cite } from './Citations'

const CATEGORY: Record<ChallengeCategory, string> = {
  operational: 'Operational',
  sales: 'Sales',
  customer_experience: 'Customer experience',
}
const LEVEL = { high: 'High', medium: 'Medium', low: 'Low' } as const

/** Numbered challenges, each laid out as Evidence → Reasoning → Impact. */
export function Challenges({ report: r }: { report: AssessmentReport }) {
  const [filter, setFilter] = useState<ChallengeCategory | 'all'>('all')
  const all = r.business_challenges
  const shown = filter === 'all' ? all : all.filter((c) => c.category === filter)
  const categories = (Object.keys(CATEGORY) as ChallengeCategory[]).filter((k) => all.some((c) => c.category === k))
  const legacy = !r.stages_completed.includes(2)

  if (!all.length) return <p className="meta">The challenge analysis hasn't run for this company yet.</p>
  return (
    <div className="max-w-[72ch]">
      {legacy && (
        <p className="meta mb-6">
          The challenge stage didn't run for this saved report, so these come from the researcher's notes.
        </p>
      )}
      {categories.length > 1 && (
        <div role="group" aria-label="Filter by category" className="no-print mb-6 flex flex-wrap gap-x-4 gap-y-1 text-sm">
          {(['all', ...categories] as const).map((k) => {
            const count = k === 'all' ? all.length : all.filter((c) => c.category === k).length
            return (
              <button
                key={k}
                type="button"
                aria-pressed={filter === k}
                onClick={() => setFilter(k)}
                className={cn(
                  'border-b py-1 [@media(pointer:coarse)]:min-h-11',
                  filter === k ? 'border-ink font-medium text-ink' : 'border-transparent text-ink-3 hover:text-ink',
                )}
              >
                {k === 'all' ? 'All' : CATEGORY[k]} <span className="num text-ink-3">{count}</span>
              </button>
            )
          })}
        </div>
      )}
      <ol className="space-y-10">
        {shown.map((c) => {
          const n = all.indexOf(c) + 1
          return (
            <li key={c.id} id={`challenge-${c.id}`}>
              <article aria-labelledby={`${c.id}-t`}>
                <h3 id={`${c.id}-t`} className="heading flex gap-3 text-[1.1875rem] text-ink">
                  <span className="num font-sans text-base font-normal text-ink-3">{n}.</span>
                  <span>
                    {c.title}
                    <Cite id={c.id} />
                  </span>
                </h3>
                <p className="meta mt-1 pl-7">
                  {CATEGORY[c.category]} · {LEVEL[c.severity]} severity · {LEVEL[c.confidence]} confidence
                </p>
                <dl className="mt-4 space-y-4 pl-7">
                  <div>
                    <dt className="text-sm font-medium text-ink-2">Evidence</dt>
                    <dd className="mt-1">
                      <ul className="space-y-1 text-[15px] text-ink">
                        {c.signals.map((s) => (
                          <li key={s} className="flex gap-2">
                            <span aria-hidden="true" className="text-ink-3">
                              –
                            </span>
                            <span className="min-w-0 [overflow-wrap:anywhere]">{s}</span>
                          </li>
                        ))}
                      </ul>
                    </dd>
                  </div>
                  <div>
                    <dt className="text-sm font-medium text-ink-2">Reasoning</dt>
                    <dd className="prose-serif mt-1 text-ink [overflow-wrap:anywhere]">{c.reasoning}</dd>
                  </div>
                  <div>
                    <dt className="text-sm font-medium text-ink-2">Impact</dt>
                    <dd className="mt-1 text-[15px] text-ink">{c.business_impact || c.description}</dd>
                  </div>
                </dl>
              </article>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
