import type { ReactNode } from 'react'

import { shortDate } from '@/lib/format'
import type { AssessmentReport } from '@/types'

/** host/…/last-segment: the middle is what differs least between sources, so it's what gets cut. */
function shortUrl(url: string): string {
  const bare = url.replace(/^https?:\/\//, '').replace(/\/$/, '')
  if (bare.length <= 70) return bare
  const [host, ...rest] = bare.split('/')
  const last = rest[rest.length - 1] ?? ''
  return `${host}/…/${last.length > 40 ? `${last.slice(0, 39)}…` : last}`
}

const NOT_FOUND = <span className="text-ink-3">Not found in the sources read</span>

/** A two-column facts table: label on the left, value on the right, hairlines between rows. */
function Facts({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="max-w-[72ch] divide-y divide-rule border-y border-rule">
      {rows.map(([label, value]) => (
        <div key={label} className="grid gap-1 py-2.5 sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-4">
          <dt className="text-sm text-ink-3">{label}</dt>
          <dd className="min-w-0 text-[15px] text-ink [overflow-wrap:anywhere]">{value || NOT_FOUND}</dd>
        </div>
      ))}
    </dl>
  )
}

function Sub({ children }: { children: ReactNode }) {
  return <h3 className="heading mt-10 mb-3 text-[1.1875rem] text-ink first:mt-0">{children}</h3>
}

export function Overview({ report: r }: { report: AssessmentReport }) {
  const ov = r.company_overview
  const sentences = ov.what_they_do.split(/(?<=[.!?])\s/)
  // The header shows the first sentence (clamped to 2 lines); repeat the whole text here only if there's more.
  const rest = sentences.length > 1 || sentences[0].length > 160 ? ov.what_they_do : ''
  return (
    <>
      {rest && <p className="prose-serif mb-8 text-ink">{rest}</p>}
      <div>
        <Facts
          rows={[
            ['Industry', [ov.industry, ov.sub_industry].filter(Boolean).join(' · ')],
            ['Business model', ov.business_model],
            ['Headquarters', ov.headquarters],
            ['Presence', ov.geographic_presence.join(', ')],
            [
              'Leadership',
              ov.leadership.length ? ov.leadership.join('; ') : (
                <span className="text-ink-3">Current leadership not confirmed by a source from the last 12 months</span>
              ),
            ],
            ['Revenue', ov.scale.revenue],
            ['Portfolio', ov.scale.projects_or_portfolio],
            ['Employees', ov.scale.employees],
            ...(ov.scale.other_metrics.length ? [['Other figures', ov.scale.other_metrics.join('; ')] as [string, ReactNode]] : []),
            ['Company size', ov.company_size],
          ]}
        />
      </div>
    </>
  )
}

export function KeyInformation({ report: r }: { report: AssessmentReport }) {
  const k = r.key_business_information
  return (
    <div className="max-w-[72ch]">
      {k.recent_developments.length > 0 && (
        <>
          <Sub>Recent developments</Sub>
          <ul className="space-y-3">
            {k.recent_developments.map((n) => (
              <li key={n.headline} className="grid gap-x-4 sm:grid-cols-[6.5rem_minmax(0,1fr)]">
                <span className="meta num pt-0.5">{n.date ? shortDate(n.date) : 'Undated'}</span>
                <span className="text-[15px] text-ink">
                  {n.source_url ? (
                    <a href={n.source_url} target="_blank" rel="noreferrer noopener" className="font-medium underline decoration-rule-strong underline-offset-4 hover:decoration-ink-2">
                      {n.headline}
                    </a>
                  ) : (
                    <span className="font-medium">{n.headline}</span>
                  )}
                  {n.summary && <span className="block text-ink-2">{n.summary}</span>}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}

      {k.major_projects.length > 0 && (
        <>
          <Sub>Major projects</Sub>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-rule-strong text-left text-ink-3">
                  <th scope="col" className="py-2 pr-4 font-normal">Project</th>
                  <th scope="col" className="py-2 pr-4 font-normal">Location</th>
                  <th scope="col" className="py-2 pr-4 font-normal">Segment</th>
                  <th scope="col" className="py-2 font-normal">Status</th>
                </tr>
              </thead>
              <tbody>
                {k.major_projects.map((p) => (
                  <tr key={p.name} className="border-b border-rule align-top">
                    <th scope="row" className="py-2 pr-4 text-left font-medium text-ink">
                      {p.name}
                      {p.details && <span className="block font-normal text-ink-3">{p.details}</span>}
                    </th>
                    <td className="py-2 pr-4 text-ink-2">{p.location ?? '—'}</td>
                    <td className="py-2 pr-4 text-ink-2">{p.segment ?? '—'}</td>
                    <td className="py-2 text-ink-2">{p.status ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {k.offerings.length > 0 && (
        <>
          <Sub>Offerings</Sub>
          <ul className="space-y-1.5 text-[15px]">
            {k.offerings.map((o) => (
              <li key={o.name}>
                <span className="font-medium text-ink">{o.name}</span>
                {o.description && <span className="text-ink-2">: {o.description}</span>}
              </li>
            ))}
          </ul>
        </>
      )}

      {k.expansion_plans.length > 0 && (
        <>
          <Sub>Expansion plans</Sub>
          <ul className="list-disc space-y-1.5 pl-5 text-[15px] text-ink marker:text-ink-3 [overflow-wrap:anywhere]">
            {k.expansion_plans.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </>
      )}

      {(k.target_audience.length > 0 || k.competitors.length > 0) && (
        <>
          <Sub>Market</Sub>
          <Facts
            rows={[
              ['Target audience', k.target_audience.join('; ')],
              ['Competitors', k.competitors.join(', ')],
            ]}
          />
        </>
      )}

      {k.public_information.length > 0 && (
        <>
          <Sub>Public record</Sub>
          <ul className="space-y-1.5 text-[15px]">
            {k.public_information.map((p) => (
              <li key={p.category + p.detail}>
                <span className="text-ink-3">{p.category}: </span>
                <span className="text-ink">{p.detail}</span>
                {p.source_url && (
                  <a href={p.source_url} target="_blank" rel="noreferrer noopener" className="ml-1 text-brand underline decoration-brand/40 underline-offset-4 hover:decoration-brand">
                    source<span className="sr-only"> (opens in a new tab)</span>
                  </a>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}

export function Sources({ report: r }: { report: AssessmentReport }) {
  const cites = r.citations ?? []
  return (
    <div className="max-w-[72ch]">
      {cites.length > 0 ? (
        <ol className="space-y-2">
          {cites.map((c) => (
            <li key={c.n} id={`source-${c.n}`} className="grid grid-cols-[2rem_minmax(0,1fr)] text-[15px]">
              <span className="num text-ink-3">{c.n}.</span>
              <span>
                <a href={c.url} target="_blank" rel="noreferrer noopener" className="text-ink underline decoration-rule-strong underline-offset-4 [overflow-wrap:anywhere] hover:decoration-ink-2">
                  {c.title || c.url}
                </a>
                <span className="meta block">
                  {c.source_type || 'source'}
                  {c.date ? ` · ${shortDate(c.date)}` : ' · undated'} ·{' '}
                  <span className="[overflow-wrap:anywhere]">{shortUrl(c.url)}</span>
                </span>
              </span>
            </li>
          ))}
        </ol>
      ) : r.sources.length > 0 ? (
        <ul className="space-y-1.5 text-[15px] break-all">
          {r.sources.map((s) => (
            <li key={s}>
              <a href={s} target="_blank" rel="noreferrer noopener" className="text-ink underline decoration-rule-strong underline-offset-4">
                {s}
              </a>
            </li>
          ))}
        </ul>
      ) : (
        <p className="meta">No sources were recorded for this report.</p>
      )}
      {r.assumptions.length > 0 && (
        <>
          <Sub>Assumptions</Sub>
          <p className="meta mb-2">Everything below is inferred, not taken from a source.</p>
          <ul className="list-disc space-y-1.5 pl-5 text-[15px] text-ink-2 marker:text-ink-3 [overflow-wrap:anywhere]">
            {r.assumptions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
