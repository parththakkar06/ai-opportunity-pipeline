import type { AssessmentReport } from '../../types'
import { Badge, MapPinIcon, qualityTone } from '../ui'
import { Chips, EmptyNote, ExternalLink, Reveal, RevealGroup, Section, StatCard } from './primitives'

export function OverviewSection({ report, entrance }: { report: AssessmentReport; entrance: boolean }) {
  const o = report.company_overview
  return (
    <RevealGroup enabled={entrance} className="space-y-5">
      <Reveal>
        <div className="rounded-2xl border border-border bg-card p-5 sm:p-7">
          <h2 className="text-sm font-semibold tracking-wide text-muted-foreground uppercase">What they do</h2>
          <p className="mt-2 max-w-prose text-lg leading-relaxed text-foreground text-pretty">{o.what_they_do}</p>
          <dl className="mt-6 grid gap-x-6 gap-y-4 border-t border-border pt-5 sm:grid-cols-2 xl:grid-cols-4">
            <Fact label="Industry" value={o.sub_industry ? `${o.industry} · ${o.sub_industry}` : o.industry} />
            <Fact label="Business model" value={o.business_model} />
            <Fact label="Headquarters" value={o.headquarters} />
            <div>
              <dt className="text-sm text-muted-foreground">Website</dt>
              <dd className="mt-0.5 text-base">
                {o.website ? <ExternalLink href={o.website}>{o.website.replace(/^https?:\/\//, '').replace(/\/$/, '')}</ExternalLink> : '—'}
              </dd>
            </div>
          </dl>
        </div>
      </Reveal>

      <Section title="Scale" description="As reported in public sources; figures keep their original currency and period.">
        <div className="grid gap-3 sm:grid-cols-3">
          <StatCard label="Revenue / bookings" value={o.scale.revenue} />
          <StatCard label="Projects / portfolio" value={o.scale.projects_or_portfolio} />
          <StatCard label="Employees" value={o.scale.employees ?? o.company_size} />
        </div>
        {o.scale.other_metrics.length > 0 && (
          <ul className="mt-4 grid gap-2 sm:grid-cols-2">
            {o.scale.other_metrics.map((m) => (
              <li key={m} className="flex gap-2 text-base text-secondary">
                <span className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" aria-hidden="true" />
                {m}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <div className="grid gap-5 lg:grid-cols-2">
        <Section
          title="Geographic presence"
          description={o.geographic_presence.length ? `${o.geographic_presence.length} locations` : undefined}
          action={<MapPinIcon className="h-5 w-5 text-muted-foreground" />}
        >
          <Chips items={o.geographic_presence} tone="accent" empty="Locations weren’t found in public sources." />
        </Section>
        <Section title="Leadership">
          {o.leadership.length ? (
            <ul className="divide-y divide-border">
              {o.leadership.map((l) => {
                const [name, role] = l.split(/\s+[—–-]\s+/)
                return (
                  <li key={l} className="flex flex-wrap items-baseline justify-between gap-x-3 py-2 first:pt-0 last:pb-0">
                    <span className="text-base font-medium text-foreground">{name}</span>
                    {role && <span className="text-sm text-muted-foreground">{role}</span>}
                  </li>
                )
              })}
            </ul>
          ) : (
            <EmptyNote>No named leaders in public sources. The pitch is addressed by title.</EmptyNote>
          )}
        </Section>
      </div>

      <Section
        title="Research basis"
        description="How much of this report rests on evidence versus inference."
        action={<Badge tone={qualityTone(report.data_quality)}>{report.data_quality} data quality</Badge>}
      >
        <div className="grid gap-5 md:grid-cols-2">
          <details className="group rounded-xl bg-subtle p-4 open:pb-4">
            <summary className="-m-2 flex min-h-11 items-center justify-between rounded-lg p-2 text-base font-semibold text-foreground marker:content-none hover:bg-muted">
              Assumptions ({report.assumptions.length})
              <span className="text-sm font-normal text-accent group-open:hidden">Show</span>
              <span className="hidden text-sm font-normal text-accent group-open:inline">Hide</span>
            </summary>
            <ul className="mt-3 space-y-2 text-base text-secondary">
              {report.assumptions.length ? report.assumptions.map((a) => <li key={a}>• {a}</li>) : <li>None recorded.</li>}
            </ul>
          </details>
          <details className="group rounded-xl bg-subtle p-4">
            <summary className="-m-2 flex min-h-11 items-center justify-between rounded-lg p-2 text-base font-semibold text-foreground marker:content-none hover:bg-muted">
              Sources ({report.sources.length})
              <span className="text-sm font-normal text-accent group-open:hidden">Show</span>
              <span className="hidden text-sm font-normal text-accent group-open:inline">Hide</span>
            </summary>
            <ul className="mt-3 space-y-2 text-sm [overflow-wrap:anywhere]">
              {report.sources.map((s) => (
                <li key={s}>
                  <ExternalLink href={s}>{s.replace(/^https?:\/\/(www\.)?/, '')}</ExternalLink>
                </li>
              ))}
            </ul>
          </details>
        </div>
      </Section>
    </RevealGroup>
  )
}

function Fact({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 text-base font-medium text-foreground">{value ?? '—'}</dd>
    </div>
  )
}
