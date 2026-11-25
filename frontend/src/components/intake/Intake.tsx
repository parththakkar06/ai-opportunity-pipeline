import { useId, useRef, useState, type FormEvent } from 'react'

import { Button } from '@/components/ui/button'
import { isValidWebsite, normalizeWebsite, relativeTime } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { SavedRun } from '@/types'

export const EXAMPLE_COMPANIES = [
  { name: 'Adani Realty', url: 'adanirealty.com' },
  { name: 'Sobha', url: 'sobha.com' },
  { name: 'Prestige Group', url: 'prestigeconstructions.com' },
  { name: 'Brigade Group', url: 'brigadegroup.com' },
  { name: 'Puravankara', url: 'puravankara.com' },
]

const QUALITY: Record<string, string> = { high: 'High data quality', medium: 'Medium data quality', low: 'Low data quality' }

/** The first screen: one question, an optional website, examples as links, and the saved reports. */
export function Intake({
  runs,
  runsLoading,
  running,
  notice,
  onAnalyze,
  onOpenRun,
  onResume,
  onHowItWorks,
}: {
  runs: SavedRun[]
  runsLoading: boolean
  running: boolean
  notice?: React.ReactNode
  onAnalyze: (company: string, url: string, includePrototype: boolean) => void
  onOpenRun: (slug: string) => void
  onResume: (run: SavedRun) => void
  onHowItWorks: () => void
}) {
  const ids = { name: useId(), url: useId(), nameError: useId(), urlError: useId(), proto: useId() }
  const [company, setCompany] = useState('')
  const [url, setUrl] = useState('')
  const [showUrl, setShowUrl] = useState(false)
  const [prototype, setPrototype] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const nameRef = useRef<HTMLInputElement>(null)
  const urlRef = useRef<HTMLInputElement>(null)

  const nameError = submitted && !company.trim() ? 'Enter a company name, or pick an example below.' : null
  const urlError = submitted && !isValidWebsite(url) ? 'Enter a website like sobha.com.' : null

  const submit = (e: FormEvent) => {
    e.preventDefault()
    setSubmitted(true)
    if (running) return
    if (!company.trim()) return nameRef.current?.focus()
    if (!isValidWebsite(url)) return urlRef.current?.focus()
    onAnalyze(company.trim(), normalizeWebsite(url), prototype)
  }

  const input =
    'w-full rounded-md border bg-sheet px-3.5 text-ink placeholder:text-ink-3 focus-visible:border-brand focus-visible:outline-none disabled:opacity-60'

  return (
    <div className="mx-auto max-w-[36rem] px-4 pt-[12vh] pb-24 sm:px-0">
      <h1 className="display text-[2.5rem] text-ink sm:text-[2.75rem]">Research a company</h1>
      <p className="prose-serif mt-3 text-ink-2">
        Get a cited brief: what the company does, its challenges, ranked AI opportunities, and a one-page pitch to
        its CEO.
      </p>
      {notice && <div className="mt-6">{notice}</div>}

      <form onSubmit={submit} noValidate className="mt-8">
        <label htmlFor={ids.name} className="sr-only">
          Company name
        </label>
        <div className="flex gap-2">
          <input
            ref={nameRef}
            id={ids.name}
            type="text"
            autoComplete="organization"
            placeholder="Company name, e.g. Sobha"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            disabled={running}
            aria-invalid={!!nameError}
            aria-describedby={nameError ? ids.nameError : undefined}
            className={cn(input, 'h-12 text-[17px]', nameError ? 'border-negative' : 'border-rule-strong')}
          />
          <Button type="submit" size="lg" disabled={running} className="h-12 shrink-0">
            {running ? 'Running…' : 'Research'}
          </Button>
        </div>
        {nameError && (
          <p id={ids.nameError} className="mt-1.5 text-sm text-negative">
            {nameError}
          </p>
        )}

        <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
          {!showUrl && (
            <button
              type="button"
              onClick={() => {
                setShowUrl(true)
                window.setTimeout(() => urlRef.current?.focus(), 0)
              }}
              className="text-brand underline-offset-4 hover:underline"
            >
              Add website
            </button>
          )}
          <label htmlFor={ids.proto} className="inline-flex items-center gap-2 text-ink-2">
            <input
              id={ids.proto}
              type="checkbox"
              checked={prototype}
              onChange={(e) => setPrototype(e.target.checked)}
              disabled={running}
              className="size-4 accent-[var(--color-brand)]"
            />
            Also build an HTML prototype <span className="text-ink-3">(slower)</span>
          </label>
        </div>

        {showUrl && (
          <div className="mt-3">
            <label htmlFor={ids.url} className="text-sm text-ink-2">
              Website <span className="text-ink-3">(locks the research onto the right company)</span>
            </label>
            <input
              ref={urlRef}
              id={ids.url}
              type="text"
              inputMode="url"
              autoComplete="url"
              spellCheck={false}
              placeholder="sobha.com"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={running}
              aria-invalid={!!urlError}
              aria-describedby={urlError ? ids.urlError : undefined}
              className={cn(input, 'mt-1 h-10 text-[15px]', urlError ? 'border-negative' : 'border-rule-strong')}
            />
            {urlError && (
              <p id={ids.urlError} className="mt-1.5 text-sm text-negative">
                {urlError}
              </p>
            )}
          </div>
        )}
      </form>

      <p className="mt-8 text-sm text-ink-3">
        Try{' '}
        {EXAMPLE_COMPANIES.map((c, i) => (
          <span key={c.name}>
            <button
              type="button"
              disabled={running}
              onClick={() => {
                setCompany(c.name)
                setUrl(c.url)
                setShowUrl(true)
                nameRef.current?.focus()
              }}
              className="text-ink-2 underline decoration-rule-strong underline-offset-4 hover:text-ink hover:decoration-ink-2 disabled:no-underline"
            >
              {c.name}
            </button>
            {i < EXAMPLE_COMPANIES.length - 1 ? ', ' : '.'}
          </span>
        ))}{' '}
        <button type="button" onClick={onHowItWorks} className="ml-1 text-brand underline-offset-4 hover:underline">
          How it works
        </button>
      </p>

      <section aria-labelledby="saved-heading" className="mt-16 border-t border-rule pt-6">
        <h2 id="saved-heading" className="heading text-xl text-ink">
          Saved reports
        </h2>
        {runsLoading ? (
          <p className="meta mt-3">Loading…</p>
        ) : runs.length === 0 ? (
          <p className="meta mt-3">None yet. Your reports appear here, and open without using any quota.</p>
        ) : (
          <ul className="mt-2 divide-y divide-rule">
            {runs.map((r) => (
              <li key={r.slug} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 py-2.5">
                <button
                  type="button"
                  onClick={() => onOpenRun(r.slug)}
                  className="text-left text-[15px] font-medium text-ink underline-offset-4 hover:underline"
                >
                  {r.business_name}
                </button>
                <span className="meta num">
                  {relativeTime(r.generated_at)} · {QUALITY[r.data_quality] ?? r.data_quality}
                  {!r.complete && ` · stages ${r.stages_completed.join(', ')} of 4`}
                </span>
                {!r.complete && r.next_stage && (
                  <Button
                    variant="link"
                    size="sm"
                    className="ml-auto"
                    disabled={running}
                    onClick={() => onResume(r)}
                    aria-label={`Resume from stage ${r.next_stage}: ${r.business_name}`}
                  >
                    Resume from stage {r.next_stage}
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
