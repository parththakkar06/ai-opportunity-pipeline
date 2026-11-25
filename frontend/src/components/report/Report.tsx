import { ChevronDown } from 'lucide-react'
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Menu, MenuItem } from '@/components/ui/menu'
import { brandAccent } from '@/lib/brand'
import { shortDate } from '@/lib/format'
import { useIsDesktop } from '@/lib/useMediaQuery'
import { cn } from '@/lib/utils'
import type { AssessmentReport, ReportPayload } from '@/types'

import { Challenges } from './Challenges'
import { Cite, CitationProvider } from './Citations'
import { Opportunities } from './Opportunities'
import { Pitch } from './Pitch'
import { KeyInformation, Overview, Sources } from './Sections'

export const SECTIONS = [
  { id: 'overview', label: 'Overview' },
  { id: 'key-information', label: 'Key information' },
  { id: 'challenges', label: 'Challenges' },
  { id: 'opportunities', label: 'Opportunities' },
  { id: 'ceo-pitch', label: 'CEO pitch' },
  { id: 'sources', label: 'Sources' },
] as const
const SECTION_IDS = SECTIONS.map((s) => s.id)

/** One scrolling document: header, cited metrics, then six sections with a scroll-spied contents list. */
export function Report({ payload, onEmail }: { payload: ReportPayload; onEmail: () => void }) {
  const r = payload.report
  const accent = brandAccent(r.brand_color)
  const isDesktop = useIsDesktop()
  const active = useScrollSpy(SECTION_IDS)
  const titleRef = useRef<HTMLHeadingElement>(null)

  // Screen-reader and keyboard users land on the report title when a report opens (unless a #section
  // link brought them here, in which case the browser scrolls to that section).
  useEffect(() => {
    if (!window.location.hash) titleRef.current?.focus({ preventScroll: true })
    else document.getElementById(window.location.hash.slice(1))?.scrollIntoView()
  }, [r.slug])

  return (
    <CitationProvider report={r}>
      <div
        style={{ '--brand': accent.light, '--brand-dark': accent.dark } as CSSProperties}
        className="mx-auto grid max-w-[1320px] gap-x-14 px-4 sm:px-6 min-[1100px]:grid-cols-[13rem_minmax(0,1fr)]"
      >
        {isDesktop ? (
          <nav aria-label="Contents" className="no-print sticky top-20 self-start pt-14">
            <p className="meta mb-2">Contents</p>
            <ol className="space-y-0.5">
              {SECTIONS.map((s, i) => (
                <li key={s.id}>
                  <a
                    href={`#${s.id}`}
                    aria-current={active === s.id ? 'location' : undefined}
                    className={cn(
                      'flex gap-2.5 border-l-2 py-1 pl-3 text-sm',
                      active === s.id ? 'border-brand font-medium text-ink' : 'border-transparent text-ink-3 hover:text-ink',
                    )}
                  >
                    <span className="num w-3 text-ink-3">{i + 1}</span>
                    {s.label}
                  </a>
                </li>
              ))}
            </ol>
          </nav>
        ) : (
          <MobileContents active={active} />
        )}

        <article id="report" aria-labelledby="report-title" className="print-full min-w-0 pt-10 pb-32 min-[1100px]:pt-14">
          <Header report={r} titleRef={titleRef} />
          {payload.legacy && (
            <p role="note" className="mt-6 max-w-[72ch] border-l-2 border-caution py-1 pl-3 text-sm text-ink">
              This report was saved before the provenance and verification checks were added, so its names and
              figures weren't checked against dated sources. Research the company again for a checked report.
            </p>
          )}
          <Metrics report={r} />
          <Section n={1} id="overview" title="Overview">
            <Overview report={r} />
          </Section>
          <Section n={2} id="key-information" title="Key information">
            <KeyInformation report={r} />
          </Section>
          <Section n={3} id="challenges" title="Business challenges">
            <Challenges report={r} />
          </Section>
          <Section n={4} id="opportunities" title="AI opportunities">
            <Opportunities report={r} />
          </Section>
          <Section n={5} id="ceo-pitch" title="CEO pitch">
            <Pitch payload={payload} onEmail={onEmail} />
          </Section>
          <Section n={6} id="sources" title="Sources and assumptions">
            <Sources report={r} />
          </Section>
        </article>
      </div>
    </CitationProvider>
  )
}

function Header({ report: r, titleRef }: { report: AssessmentReport; titleRef: React.Ref<HTMLHeadingElement> }) {
  const ov = r.company_overview
  const firstSentence = ov.what_they_do.split(/(?<=[.!?])\s/)[0]
  const v = r.verification
  const partial = r.stages_completed.length < 4
  return (
    <header>
      <h1 id="report-title" ref={titleRef} tabIndex={-1} translate="no" className="display text-[2.25rem] text-ink sm:text-[2.75rem]">
        {r.business_name}
      </h1>
      <p className="prose-serif mt-2 line-clamp-2 text-ink-2" title={firstSentence}>{firstSentence}</p>
      <p className="meta mt-3 flex flex-wrap gap-x-2 [&>*:not(:last-child)]:after:ml-2 [&>*:not(:last-child)]:after:content-['·']">
        {ov.website && (
          <a
            href={ov.website.startsWith('http') ? ov.website : `https://${ov.website}`}
            target="_blank"
            rel="noreferrer noopener"
            className="min-w-0 text-ink-2 underline decoration-rule-strong underline-offset-4 [overflow-wrap:anywhere] hover:decoration-ink-2"
          >
            {ov.website.replace(/^https?:\/\//, '').replace(/\/$/, '')}
          </a>
        )}
        <span>{ov.industry}</span>
        {r.generated_at && <span>Researched {shortDate(r.generated_at)}</span>}
      </p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        <Badge variant={r.data_quality === 'high' ? 'positive' : r.data_quality === 'low' ? 'caution' : 'default'}>
          {r.data_quality[0].toUpperCase() + r.data_quality.slice(1)} data quality
        </Badge>
        {v && v.pass_rate != null && (
          <Badge variant={v.pass_rate >= 0.8 ? 'positive' : 'caution'}>
            Verified {v.supported}/{v.checked} claims
          </Badge>
        )}
        {partial && <Badge variant="caution">Partial: stages {r.stages_completed.join(', ')} of 4</Badge>}
      </div>
    </header>
  )
}

/** 3–5 headline figures, each cited and dated. Not shown at all when fewer than 3 are backed by facts. */
function Metrics({ report: r }: { report: AssessmentReport }) {
  const metrics = r.key_metrics ?? []
  if (metrics.length < 3) return null
  return (
    <dl className="mt-10 grid grid-cols-2 border-y border-rule sm:grid-cols-3 lg:grid-cols-5">
      {metrics.map((m) => (
        <div key={m.label + m.value} className="flex flex-col border-rule py-4 pr-4 not-first:sm:border-l sm:pl-4 sm:first:pl-0">
          <dt className="order-2 mt-0.5 text-[13px] text-ink-2">{m.label}</dt>
          <dd className="order-1">
            <span className="num block text-lg leading-tight font-semibold tracking-[-0.01em] text-ink sm:text-[1.375rem]">{m.value}</span>
            <span className="meta num">
              {m.date ? `as of ${shortDate(m.date)}` : 'undated'}
              <Cite nums={m.citations} facts={m.facts} />
            </span>
          </dd>
        </div>
      ))}
    </dl>
  )
}

function Section({ n, id, title, children }: { n: number; id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-h`} className="mt-16 border-t border-rule pt-8">
      <h2 id={`${id}-h`} className="heading flex items-baseline gap-3 text-[1.625rem] text-ink">
        <span className="num font-sans text-base font-normal text-ink-3">{n}</span>
        {title}
      </h2>
      <div className="mt-6">{children}</div>
    </section>
  )
}

function MobileContents({ active }: { active: string }) {
  const current = SECTIONS.find((s) => s.id === active) ?? SECTIONS[0]
  return (
    <div className="no-print sticky top-14 z-10 -mx-4 border-b border-rule bg-paper/95 px-4 py-1.5 backdrop-blur-sm sm:-mx-6 sm:px-6">
      <Menu
        label="Contents"
        align="start"
        trigger={(props) => (
          <Button variant="ghost" size="sm" {...props}>
            <span className="text-ink-3">Contents:</span> {current.label}
            <ChevronDown strokeWidth={1.5} aria-hidden="true" />
          </Button>
        )}
      >
        {(close) =>
          SECTIONS.map((s) => (
            <MenuItem key={s.id} href={`#${s.id}`} onSelect={close}>
              {s.label}
            </MenuItem>
          ))
        }
      </Menu>
    </div>
  )
}

/** The section whose top most recently crossed just below the nav. */
function useScrollSpy(ids: readonly string[]): string {
  const [active, setActive] = useState(ids[0])
  useEffect(() => {
    const elements = ids.map((id) => document.getElementById(id)).filter(Boolean) as HTMLElement[]
    const onScroll = () => {
      const line = 140 // nav (56px) + the 80px scroll padding anchors land at, plus a little slack
      let current = ids[0]
      for (const el of elements) if (el.getBoundingClientRect().top - line <= 0) current = el.id
      // At the very bottom, the last section is the one being read even if its top never reaches the line.
      if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4) current = ids[ids.length - 1]
      setActive(current)
    }
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
    }
  }, [ids])
  return active
}
