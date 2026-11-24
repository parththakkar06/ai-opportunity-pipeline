import type { AssessmentReport, PublicInfoItem } from '../../types'
import { ArrowRightIcon } from '../ui'
import { Chips, EmptyNote, ExternalLink, RevealGroup, Section } from './primitives'

export function KeyInfoSection({ report, entrance }: { report: AssessmentReport; entrance: boolean }) {
  const k = report.key_business_information
  const publicByCategory = groupBy(k.public_information, (i) => i.category)

  return (
    <RevealGroup enabled={entrance} className="space-y-5">
      <Section title="Major offerings" description={`${k.offerings.length} lines of business`}>
        <ul className="grid gap-3 sm:grid-cols-2">
          {k.offerings.map((o) => (
            <li key={o.name} className="rounded-xl border border-border bg-subtle p-4">
              <p className="text-base font-semibold text-foreground">{o.name}</p>
              <p className="mt-1 text-base text-secondary">{o.description}</p>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Major projects" description={k.major_projects.length ? `${k.major_projects.length} named in public sources` : undefined}>
        {k.major_projects.length === 0 ? (
          <EmptyNote>No specific projects were named in public sources.</EmptyNote>
        ) : (
          <>
            {/* Table from md up; stacked cards on phones. */}
            <div className="hidden overflow-x-auto md:block" tabIndex={0} role="region" aria-label="Major projects table">
              <table className="w-full text-left text-base">
                <caption className="sr-only">Major projects</caption>
                <thead>
                  <tr className="border-b border-border text-sm text-muted-foreground">
                    {['Project', 'Location', 'Segment', 'Status', 'Details'].map((h) => (
                      <th key={h} scope="col" className="py-2 pr-4 font-medium">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {k.major_projects.map((p) => (
                    <tr key={p.name} className="align-top">
                      <th scope="row" className="py-3 pr-4 font-semibold text-foreground">
                        {p.name}
                      </th>
                      <td className="py-3 pr-4 text-secondary">{p.location ?? '—'}</td>
                      <td className="py-3 pr-4 text-secondary">{p.segment ?? '—'}</td>
                      <td className="py-3 pr-4 text-secondary">{p.status ?? '—'}</td>
                      <td className="py-3 text-secondary">{p.details ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ul className="space-y-3 md:hidden">
              {k.major_projects.map((p) => (
                <li key={p.name} className="rounded-xl border border-border bg-subtle p-4">
                  <p className="text-base font-semibold text-foreground">{p.name}</p>
                  <p className="mt-0.5 text-sm text-muted-foreground">
                    {[p.location, p.segment, p.status].filter(Boolean).join(' · ') || '—'}
                  </p>
                  {p.details && <p className="mt-2 text-base text-secondary">{p.details}</p>}
                </li>
              ))}
            </ul>
          </>
        )}
      </Section>

      <div className="grid gap-5 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <Section title="Recent developments">
            {k.recent_developments.length === 0 ? (
              <EmptyNote>No recent news was found.</EmptyNote>
            ) : (
              <ol className="relative space-y-5 border-l-2 border-border pl-5">
                {k.recent_developments.map((n) => (
                  <li key={n.headline} className="relative">
                    <span className="absolute top-1.5 -left-[27px] h-3 w-3 rounded-full border-2 border-card bg-accent" aria-hidden="true" />
                    {n.date && <p className="text-sm font-medium text-muted-foreground tabular-nums">{n.date}</p>}
                    <p className="text-base font-semibold text-foreground">
                      {n.source_url ? <ExternalLink href={n.source_url}>{n.headline}</ExternalLink> : n.headline}
                    </p>
                    <p className="mt-0.5 text-base text-secondary">{n.summary}</p>
                  </li>
                ))}
              </ol>
            )}
          </Section>
        </div>
        <div className="lg:col-span-2">
          <Section title="Expansion plans">
            {k.expansion_plans.length === 0 ? (
              <EmptyNote>Nothing announced publicly.</EmptyNote>
            ) : (
              <ul className="space-y-3">
                {k.expansion_plans.map((e) => (
                  <li key={e} className="flex gap-2.5 text-base text-secondary">
                    <ArrowRightIcon className="mt-1 h-4 w-4 shrink-0 text-accent" />
                    {e}
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </div>
      </div>

      <Section
        title="Important public information"
        description="Regulatory filings (e.g. RERA), partnerships, financials and other material facts."
      >
        {k.public_information.length === 0 ? (
          <EmptyNote>None found.</EmptyNote>
        ) : (
          <div className="grid gap-5 md:grid-cols-2">
            {Object.entries(publicByCategory).map(([category, items]) => (
              <div key={category}>
                <h3 className="text-sm font-semibold tracking-wide text-muted-foreground uppercase">{category}</h3>
                <ul className="mt-2 space-y-2">
                  {items.map((i) => (
                    <li key={i.detail} className="text-base text-secondary">
                      {i.source_url ? <ExternalLink href={i.source_url}>{i.detail}</ExternalLink> : i.detail}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </Section>

      <div className="grid gap-5 lg:grid-cols-2">
        <Section title="Target audience">
          <Chips items={k.target_audience} empty="Not identified." />
        </Section>
        <Section title="Competitors">
          <Chips items={k.competitors} empty="Not identified." />
        </Section>
      </div>
    </RevealGroup>
  )
}

function groupBy(items: PublicInfoItem[], key: (i: PublicInfoItem) => string): Record<string, PublicInfoItem[]> {
  return items.reduce<Record<string, PublicInfoItem[]>>((acc, item) => {
    const k = key(item).trim() || 'Other'
    ;(acc[k] ??= []).push(item)
    return acc
  }, {})
}
