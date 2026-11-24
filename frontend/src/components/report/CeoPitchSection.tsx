import { useId, type ReactNode } from 'react'
import type { AssessmentReport } from '../../types'
import { Button, Card, CheckIcon, CopyIcon, PrinterIcon } from '../ui'
import { EmptyNote, Reveal, RevealGroup } from './primitives'

interface Props {
  report: AssessmentReport
  entrance: boolean
  onPrint: () => void
  onCopy: () => void
  copied: boolean
  includeKit: boolean
  onIncludeKitChange: (value: boolean) => void
}

export function CeoPitchSection({ report, entrance, onPrint, onCopy, copied, includeKit, onIncludeKitChange }: Props) {
  const kitId = useId()
  const p = report.ceo_pitch
  if (!p)
    return (
      <Card className="p-6">
        <EmptyNote>The CEO Pitch Builder hasn’t run for this company yet. Resume the run to generate the one-page pitch.</EmptyNote>
      </Card>
    )
  return (
    <RevealGroup enabled={entrance} className="space-y-6">
      <Reveal>
        <div className="no-print mx-auto flex max-w-[46rem] flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap gap-2">
            <Button variant="primary" onClick={onPrint}>
              <PrinterIcon />
              Print / Save as PDF
            </Button>
            <Button onClick={onCopy} className="min-w-[8.5rem]">
              {copied ? <CheckIcon /> : <CopyIcon />}
              {copied ? 'Copied' : 'Copy pitch'}
            </Button>
          </div>
          <div className="flex items-center gap-2.5">
            <input
              id={kitId}
              type="checkbox"
              checked={includeKit}
              onChange={(e) => onIncludeKitChange(e.target.checked)}
              className="h-5 w-5 rounded accent-accent"
            />
            <label htmlFor={kitId} className="text-sm text-secondary">
              Include email &amp; elevator pitch (page 2)
            </label>
          </div>
        </div>
      </Reveal>
      <Reveal>
        <article
          id="ceo-pitch-page"
          aria-labelledby="ceo-pitch-title"
          className="mx-auto max-w-[46rem] rounded-2xl border border-border bg-card px-6 py-8 shadow-sm sm:px-12 sm:py-12"
        >
          <p className="text-xs font-semibold tracking-widest text-accent uppercase">One-page executive pitch</p>
          <h2 id="ceo-pitch-title" className="mt-2 text-2xl leading-tight font-bold text-foreground sm:text-3xl">
            {p.title}
          </h2>
          <p className="mt-3 text-base text-muted-foreground">
            To: <span className="font-semibold text-foreground">{p.addressed_to}</span>, {report.business_name}
          </p>

          <PitchBlock letter="A" title="Why we reached out">
            {p.opening ? (
              <p className="mb-3 text-base leading-relaxed text-foreground">
                {p.opening.text}{' '}
                <span className="font-mono text-xs text-muted-foreground" title="Source id in the research evidence">
                  [{p.opening.source_id}]
                </span>
              </p>
            ) : null}
            <p className="text-base leading-relaxed text-secondary">{p.why_we_reached_out}</p>
            {!p.ceo_statements_found ? (
              <p className="mt-3 text-sm text-muted-foreground italic">
                No CEO statements found in the sources read
                {p.opening ? '; the pitch opens on the newest cited fact.' : '.'}
              </p>
            ) : null}
          </PitchBlock>

          <PitchBlock letter="B" title="Opportunities we identified">
            <ul className="space-y-3">
              {p.opportunities_identified.map((o) => (
                <li key={o.title} className="flex gap-3 text-base text-secondary">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" aria-hidden="true" />
                  <span>
                    <span className="font-semibold text-foreground">{o.title}.</span> {o.evidence}
                  </span>
                </li>
              ))}
            </ul>
          </PitchBlock>

          <PitchBlock letter="C" title="What we recommend">
            <ol className="space-y-5">
              {p.recommended_solutions.map((s, i) => (
                <li key={s.name} className="flex gap-3">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent text-sm font-bold text-on-accent">
                    {i + 1}
                  </span>
                  <div className="min-w-0">
                    <p className="text-base font-semibold text-foreground">{s.name}</p>
                    <p className="text-sm text-muted-foreground">{s.maps_to}</p>
                    <p className="mt-1 text-base text-secondary">{s.what_it_does}</p>
                    <dl className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-sm">
                      <div>
                        <dt className="inline text-muted-foreground">Impact: </dt>
                        <dd className="inline font-medium text-foreground">{s.expected_impact}</dd>
                      </div>
                      <div>
                        <dt className="inline text-muted-foreground">Timeline: </dt>
                        <dd className="inline font-medium text-foreground">{s.timeline}</dd>
                      </div>
                    </dl>
                  </div>
                </li>
              ))}
            </ol>
          </PitchBlock>

          {p.roi_headline && (
            <p className="mt-8 rounded-xl bg-success-soft p-4 text-base text-success-foreground ring-1 ring-success/30">
              <span className="font-semibold">The numbers: </span>
              {p.roi_headline}.
            </p>
          )}
          <p className="mt-8 text-base leading-relaxed text-secondary">{p.closing}</p>
          <p className="mt-6 text-base text-muted-foreground">[Your Name]</p>
          <p className="mt-10 hidden border-t border-border pt-3 text-xs text-muted-foreground print:block">
            Prepared for {p.addressed_to}, {report.business_name}
            {report.generated_at &&
              ` · ${new Date(report.generated_at).toLocaleDateString(undefined, { dateStyle: 'long' })}`}
          </p>
        </article>
      </Reveal>

      <div className="print-kit mx-auto grid max-w-[46rem] gap-5 md:grid-cols-2">
        <Reveal>
          <Card className="h-full p-5 sm:p-6">
            <h3 className="text-sm font-semibold tracking-wide text-muted-foreground uppercase">Cold email</h3>
            <p className="mt-3 text-base font-semibold text-foreground">Subject: {p.email_subject}</p>
            <p className="mt-2 text-base whitespace-pre-line text-secondary">{p.email_body}</p>
          </Card>
        </Reveal>
        <Reveal>
          <Card className="h-full p-5 sm:p-6">
            <h3 className="text-sm font-semibold tracking-wide text-muted-foreground uppercase">60-second elevator pitch</h3>
            <p className="mt-3 text-base leading-relaxed whitespace-pre-line text-secondary">{p.elevator_pitch}</p>
          </Card>
        </Reveal>
      </div>
    </RevealGroup>
  )
}

function PitchBlock({ letter, title, children }: { letter: string; title: string; children: ReactNode }) {
  return (
    <section className="mt-9">
      <h3 className="flex items-center gap-2.5 text-sm font-bold tracking-wide text-foreground uppercase">
        <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary text-xs text-on-primary" aria-hidden="true">
          {letter}
        </span>
        {title}
      </h3>
      <div className="mt-3">{children}</div>
    </section>
  )
}
