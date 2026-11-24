import { useId, useState, type FormEvent } from 'react'
import { initials, isValidWebsite, normalizeWebsite } from '../../lib/format'
import { Button, Card, Spinner, cx } from '../ui'

export const EXAMPLE_COMPANIES = [
  { name: 'Adani Realty', url: 'adanirealty.com' },
  { name: 'Sobha', url: 'sobha.com' },
  { name: 'Prestige Group', url: 'prestigeconstructions.com' },
  { name: 'Brigade Group', url: 'brigadegroup.com' },
  { name: 'Puravankara', url: 'puravankara.com' },
]

interface Props {
  running: boolean
  onAnalyze: (company: string, url: string, includePrototype: boolean) => void
  onCancel: () => void
}

const inputClass =
  'mt-1.5 w-full rounded-lg border bg-card px-3 py-2.5 text-base text-foreground shadow-sm transition-colors duration-150 placeholder:text-muted-foreground disabled:bg-subtle sm:text-sm'

export function CompanyPicker({ running, onAnalyze, onCancel }: Props) {
  const ids = { name: useId(), url: useId(), nameError: useId(), urlError: useId(), urlHelp: useId(), proto: useId() }
  const [company, setCompany] = useState('')
  const [url, setUrl] = useState('')
  const [includePrototype, setIncludePrototype] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [urlTouched, setUrlTouched] = useState(false)

  const nameError = submitted && !company.trim() ? 'Enter a company name, or pick one above.' : null
  const urlError = (urlTouched || submitted) && !isValidWebsite(url) ? 'Enter a website like sobha.com.' : null

  const submit = (e: FormEvent) => {
    e.preventDefault()
    setSubmitted(true)
    if (running || !company.trim() || !isValidWebsite(url)) return
    onAnalyze(company.trim(), normalizeWebsite(url), includePrototype)
  }

  return (
    <Card className="p-5">
      <form onSubmit={submit} noValidate className="space-y-5" aria-label="New analysis">
        <fieldset>
          <legend className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Example companies
          </legend>
          <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
            {EXAMPLE_COMPANIES.map((c) => {
              const selected = company === c.name
              return (
                <button
                  key={c.name}
                  type="button"
                  disabled={running}
                  aria-pressed={selected}
                  onClick={() => {
                    setCompany(c.name)
                    setUrl(c.url)
                    setUrlTouched(false)
                  }}
                  className={cx(
                    'flex min-h-11 items-center gap-2.5 rounded-xl px-2.5 py-2 text-left text-sm font-medium ring-1 ring-inset transition-colors duration-150 disabled:opacity-50',
                    selected
                      ? 'bg-accent-soft text-accent-soft-foreground ring-accent'
                      : 'bg-card text-secondary ring-border hover:bg-subtle hover:ring-border-strong',
                  )}
                >
                  <span
                    className={cx(
                      'flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-xs font-bold',
                      selected ? 'bg-accent text-on-accent' : 'bg-muted text-secondary',
                    )}
                    aria-hidden="true"
                  >
                    {initials(c.name)}
                  </span>
                  <span className="min-w-0 truncate">{c.name}</span>
                </button>
              )
            })}
          </div>
        </fieldset>

        <div>
          <label htmlFor={ids.name} className="text-sm font-semibold text-foreground">
            Company name
          </label>
          <input
            id={ids.name}
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            placeholder="e.g. Sobha"
            autoComplete="organization"
            disabled={running}
            aria-invalid={!!nameError}
            aria-describedby={nameError ? ids.nameError : undefined}
            className={cx(inputClass, nameError ? 'border-danger' : 'border-border-strong')}
          />
          {nameError && (
            <p id={ids.nameError} className="mt-1.5 text-sm text-danger-foreground">
              {nameError}
            </p>
          )}
        </div>

        <div>
          <label htmlFor={ids.url} className="text-sm font-semibold text-foreground">
            Website <span className="font-normal text-muted-foreground">(optional)</span>
          </label>
          <input
            id={ids.url}
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onBlur={() => setUrlTouched(true)}
            placeholder="e.g. sobha.com"
            inputMode="url"
            autoComplete="url"
            spellCheck={false}
            disabled={running}
            aria-invalid={!!urlError}
            aria-describedby={urlError ? ids.urlError : ids.urlHelp}
            className={cx(inputClass, urlError ? 'border-danger' : 'border-border-strong')}
          />
          {urlError ? (
            <p id={ids.urlError} className="mt-1.5 text-sm text-danger-foreground">
              {urlError}
            </p>
          ) : (
            <p id={ids.urlHelp} className="mt-1.5 text-sm text-muted-foreground">
              Locks the research onto the right company when names are common.
            </p>
          )}
        </div>

        <div className="flex items-start gap-3 rounded-xl bg-subtle p-3">
          <input
            id={ids.proto}
            type="checkbox"
            checked={includePrototype}
            onChange={(e) => setIncludePrototype(e.target.checked)}
            disabled={running}
            className="mt-0.5 h-5 w-5 shrink-0 rounded accent-accent"
          />
          <label htmlFor={ids.proto} className="text-sm text-foreground">
            Also build an interactive HTML prototype
            <span className="mt-0.5 block text-muted-foreground">Adds a few minutes and extra requests to stage 4.</span>
          </label>
        </div>

        <div className="space-y-2">
          <div className="flex gap-2">
            <Button type="submit" variant="primary" disabled={running} className="flex-1">
              {running && <Spinner />}
              {running ? 'Analyzing…' : 'Run analysis'}
            </Button>
            {running && <Button onClick={onCancel}>Stop</Button>}
          </div>
          <p className="text-center text-sm text-muted-foreground">
            Uses your AI model and web-search quota. Saved reports below are free to open.
          </p>
        </div>
      </form>
    </Card>
  )
}
