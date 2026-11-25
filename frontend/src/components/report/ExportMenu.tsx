import { useEffect, useId, useRef, useState } from 'react'
import { useToast } from '../shell/Toast'
import { Button, CheckIcon, CopyIcon, DownloadIcon, ExternalIcon, cx } from '../ui'

// Every export is built on the server from the saved run (api/exports.py); nothing here calls a model.
const base = (slug: string) => `/api/examples/${encodeURIComponent(slug)}/export`

type EmailDraft = {
  subject: string
  body: string
  words: number
  gmail_url: string
  mailto_url: string
  mailto_shortened: boolean
}

const FILES = [
  { kind: 'pitch.pdf', label: 'One-page pitch', hint: 'PDF, 1 page' },
  { kind: 'report.pdf', label: 'Full report', hint: 'PDF with citations' },
  { kind: 'pptx', label: 'Pitch deck', hint: 'PowerPoint, 10 slides' },
  { kind: 'zip', label: 'Download all', hint: 'ZIP of all files' },
] as const

export function ExportMenu({ slug, hasPitch, onEmail }: { slug: string; hasPitch: boolean; onEmail: () => void }) {
  const [open, setOpen] = useState(false)
  const menuId = useId()
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === 'Escape' : !ref.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', close)
    }
  }, [open])

  return (
      <div ref={ref} className="relative">
        <Button aria-expanded={open} aria-controls={menuId} onClick={() => setOpen((v) => !v)} disabled={!hasPitch}>
          <DownloadIcon />
          Export
        </Button>
        {open && (
          <div
            id={menuId}
            className="absolute right-0 z-30 mt-2 w-64 rounded-xl border border-border bg-card p-1.5 shadow-lg"
          >
            {FILES.map((f) => (
              <a
                key={f.kind}
                href={`${base(slug)}/${f.kind}`}
                download
                onClick={() => setOpen(false)}
                className="flex min-h-11 flex-col justify-center rounded-lg px-3 py-1.5 hover:bg-subtle focus-visible:bg-subtle"
              >
                <span className="text-sm font-semibold text-foreground">{f.label}</span>
                <span className="text-xs text-muted-foreground">{f.hint}</span>
              </a>
            ))}
            <button
              type="button"
              onClick={() => {
                setOpen(false)
                onEmail()
              }}
              className="flex min-h-11 w-full flex-col justify-center rounded-lg px-3 py-1.5 text-left hover:bg-subtle focus-visible:bg-subtle"
            >
              <span className="text-sm font-semibold text-foreground">Email draft…</span>
              <span className="text-xs text-muted-foreground">Gmail, Mail app or .eml; never sent</span>
            </button>
          </div>
        )}
      </div>
  )
}

export function EmailPanel({ slug, onClose }: { slug: string; onClose: () => void }) {
  const { notify } = useToast()
  const [to, setTo] = useState('') // empty by default: the user chooses the recipient
  const [draft, setDraft] = useState<EmailDraft | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const toId = useId()
  const titleId = useId()
  const toRef = useRef<HTMLInputElement>(null)

  useEffect(() => toRef.current?.focus(), [])
  useEffect(() => {
    const ctrl = new AbortController()
    const t = window.setTimeout(async () => {
      try {
        const res = await fetch(`${base(slug)}/email?to=${encodeURIComponent(to)}`, { signal: ctrl.signal })
        if (!res.ok) throw new Error((await res.json()).detail ?? res.statusText)
        setDraft(await res.json())
        setError(null)
      } catch (e) {
        if (!ctrl.signal.aborted) setError(e instanceof Error ? e.message : 'Couldn’t load the email draft.')
      }
    }, 250)
    return () => {
      ctrl.abort()
      window.clearTimeout(t)
    }
  }, [slug, to])

  const copy = async () => {
    if (!draft) return
    try {
      await navigator.clipboard.writeText(`Subject: ${draft.subject}\n\n${draft.body}`)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    } catch {
      notify({ tone: 'error', title: 'Couldn’t copy', description: 'Your browser blocked clipboard access.' })
    }
  }

  const link = 'inline-flex min-h-11 items-center gap-2 rounded-lg px-4 text-sm font-semibold ring-1 ring-inset'
  return (
    <section
      aria-labelledby={titleId}
      className="mt-5 rounded-xl border border-border bg-subtle/60 p-4 sm:p-5"
      onKeyDown={(e) => e.key === 'Escape' && onClose()}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 id={titleId} className="text-base font-semibold text-foreground">
            Email draft
          </h2>
          <p className="text-sm text-muted-foreground">Nothing is sent from here. You review and send it yourself.</p>
        </div>
        <Button onClick={onClose} className="px-3">
          Close
        </Button>
      </div>
      <label htmlFor={toId} className="mt-4 block text-sm font-medium text-foreground">
        To
      </label>
      <input
        ref={toRef}
        id={toId}
        type="email"
        inputMode="email"
        autoComplete="off"
        placeholder="name@company.com"
        value={to}
        onChange={(e) => setTo(e.target.value)}
        className="mt-1 w-full rounded-lg border border-border-strong bg-card px-3 py-2.5 text-base text-foreground"
      />
      {error && <p className="mt-3 text-sm text-danger">{error}</p>}
      {draft && (
        <>
          <p className="mt-4 text-sm font-semibold text-foreground">Subject: {draft.subject}</p>
          <p className="mt-2 max-h-56 overflow-auto rounded-lg bg-card p-3 text-sm whitespace-pre-line text-secondary">
            {draft.body}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            {draft.words} words{draft.mailto_shortened ? ' · shortened for the Mail app link; the PDF has the full note' : ''}
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <a href={draft.gmail_url} target="_blank" rel="noreferrer noopener" className={cx(link, 'ring-border-strong text-secondary hover:bg-card')}>
              <ExternalIcon />
              Open in Gmail<span className="sr-only"> (opens in a new tab)</span>
            </a>
            <a href={draft.mailto_url} className={cx(link, 'ring-border-strong text-secondary hover:bg-card')}>
              Open in Mail app
            </a>
            <Button onClick={copy}>
              {copied ? <CheckIcon /> : <CopyIcon />}
              {copied ? 'Copied' : 'Copy'}
            </Button>
            <a
              href={`${base(slug)}/eml?to=${encodeURIComponent(to)}`}
              download
              className={cx(link, 'ring-border-strong text-secondary hover:bg-card')}
            >
              <DownloadIcon />
              Download .eml (with PDF)
            </a>
          </div>
        </>
      )}
    </section>
  )
}
