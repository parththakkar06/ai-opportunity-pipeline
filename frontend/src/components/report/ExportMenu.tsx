import { Check, Copy, Download, ExternalLink, X } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'

import { useToast } from '@/components/shell/Toast'
import { Button } from '@/components/ui/button'
import { Menu, MenuItem, MenuSeparator } from '@/components/ui/menu'
import { STATIC, exportUrl } from '@/lib/static'
import { gmailUrl, mailtoUrl } from '@/lib/mail'
import type { ReportPayload } from '@/types'

// Every file is built on the server from the saved run (api/exports.py); nothing here calls a model.

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
}

function downloadText(filename: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/markdown;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

/** The one place for copy, print and every download (replaces the old duplicated buttons). */
export function ExportMenu({
  payload,
  onEmail,
  variant = 'secondary',
  compactLabel = false,
}: {
  payload: ReportPayload
  onEmail: () => void
  variant?: 'secondary' | 'default'
  compactLabel?: boolean
}) {
  const { notify } = useToast()
  const r = payload.report
  const hasPitch = !!r.ceo_pitch
  return (
    <Menu
      label="Export"
      trigger={(props) => (
        <Button variant={variant} size="sm" {...props}>
          <Download strokeWidth={1.5} aria-hidden="true" />
          <span className={compactLabel ? 'sr-only sm:not-sr-only' : undefined}>Export</span>
        </Button>
      )}
    >
      {(close) => (
        <>
          {hasPitch && (
            <>
              <MenuItem
                onSelect={async () => {
                  close()
                  const ok = await copyText(payload.pitch_text)
                  notify(ok ? { tone: 'success', title: 'Pitch copied' } : { tone: 'error', title: "Couldn't copy", description: 'Your browser blocked clipboard access.' })
                }}
              >
                Copy pitch text
              </MenuItem>
              <MenuItem href={exportUrl(r.slug, 'pitch.pdf')} external onSelect={close} hint="Opens the PDF; print from there">
                Print pitch
              </MenuItem>
              <MenuItem onSelect={() => { close(); onEmail() }} hint="Gmail, Mail app or .eml. Never sent.">
                Email draft…
              </MenuItem>
              <MenuSeparator />
              <MenuItem href={exportUrl(r.slug, 'pitch.pdf')} download onSelect={close} hint="PDF, exactly 1 page">
                One-page pitch
              </MenuItem>
            </>
          )}
          <MenuItem href={exportUrl(r.slug, 'report.pdf')} download onSelect={close} hint="PDF with numbered sources">
            Full report
          </MenuItem>
          {hasPitch && (
            <MenuItem href={exportUrl(r.slug, 'pptx')} download onSelect={close} hint="PowerPoint, 10 slides">
              Pitch deck
            </MenuItem>
          )}
          <MenuItem onSelect={() => { close(); downloadText(`${r.slug}-assessment.md`, payload.markdown) }} hint="Markdown">
            Report text
          </MenuItem>
          {hasPitch && (
            <MenuItem href={exportUrl(r.slug, 'zip')} download onSelect={close} hint="ZIP of all files">
              Download all
            </MenuItem>
          )}
        </>
      )}
    </Menu>
  )
}

type EmailDraft = { subject: string; body: string; words: number; gmail_url: string; mailto_url: string; mailto_shortened: boolean }

/** Email draft in a side sheet. The To field starts empty; nothing is ever sent from the app. */
export function EmailSheet({ slug, onClose }: { slug: string; onClose: () => void }) {
  const { notify } = useToast()
  const [to, setTo] = useState('')
  const [draft, setDraft] = useState<EmailDraft | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [closing, setClosing] = useState(false)
  const ids = { title: useId(), to: useId() }
  const toRef = useRef<HTMLInputElement>(null)
  const sheetRef = useRef<HTMLDivElement>(null)
  const returnFocus = useRef<HTMLElement | null>(document.activeElement as HTMLElement | null)
  const emailUrl = exportUrl(slug, 'email')

  // In the static snapshot the links are built here from the typed recipient; the live server sends them.
  const view: EmailDraft | null = draft && STATIC
    ? {
        ...draft,
        gmail_url: gmailUrl(draft.subject, draft.body, to),
        mailto_url: mailtoUrl(draft.subject, draft.body, to).url,
        mailto_shortened: mailtoUrl(draft.subject, draft.body, to).cut,
      }
    : draft

  const close = () => {
    setClosing(true)
    window.setTimeout(() => {
      onClose()
      returnFocus.current?.focus?.()
    }, 200)
  }

  useEffect(() => {
    toRef.current?.focus()
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [])

  useEffect(() => {
    const ctrl = new AbortController()
    // Live app: the server builds the links for the typed recipient. Static snapshot: one file, links built below.
    const t = window.setTimeout(async () => {
      try {
        const res = await fetch(STATIC ? emailUrl : `${emailUrl}?to=${encodeURIComponent(to)}`, { signal: ctrl.signal })
        if (!res.ok) throw new Error(STATIC ? res.statusText : ((await res.json()).detail ?? res.statusText))
        setDraft(await res.json())
        setError(null)
      } catch (e) {
        if (!ctrl.signal.aborted) setError(e instanceof Error ? e.message : 'Couldn’t load the email draft.')
      }
    }, STATIC ? 0 : 250)
    return () => {
      ctrl.abort()
      window.clearTimeout(t)
    }
  }, [emailUrl, STATIC ? '' : to])

  // Keep Tab inside the sheet while it's open.
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') return close()
    if (e.key !== 'Tab') return
    const f = sheetRef.current?.querySelectorAll<HTMLElement>('a[href], button:not(:disabled), input, [tabindex="0"]')
    if (!f?.length) return
    const first = f[0]
    const last = f[f.length - 1]
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault()
      last.focus()
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault()
      first.focus()
    }
  }

  const link = 'pressable inline-flex h-9 items-center gap-2 rounded-md border border-input bg-sheet px-3.5 text-sm font-medium text-ink-2 hover:bg-tint hover:text-ink [@media(pointer:coarse)]:min-h-11'
  return (
    <div className="no-print fixed inset-0 z-50" onKeyDown={onKeyDown}>
      <div
        aria-hidden="true"
        onClick={close}
        className={`absolute inset-0 bg-ink/20 transition-opacity duration-200 ${closing ? 'opacity-0' : 'rise-in'}`}
      />
      <div
        ref={sheetRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={ids.title}
        className={`absolute inset-y-0 right-0 flex w-full max-w-[30rem] flex-col border-l border-rule bg-sheet shadow-float transition-transform duration-200 ease-[var(--ease-drawer)] motion-reduce:transition-none ${
          closing ? 'translate-x-full' : 'sheet-in'
        }`}
      >
        <div className="flex items-start justify-between gap-3 border-b border-rule p-5">
          <div>
            <h2 id={ids.title} className="heading text-xl text-ink">
              Email draft
            </h2>
            <p className="meta mt-1">Nothing is sent from here. Review it and send it yourself.</p>
          </div>
          <Button variant="ghost" size="icon" onClick={close} aria-label="Close email draft">
            <X strokeWidth={1.5} aria-hidden="true" />
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto p-5">
          <label htmlFor={ids.to} className="text-sm font-medium text-ink-2">
            To
          </label>
          <input
            ref={toRef}
            id={ids.to}
            type="email"
            inputMode="email"
            autoComplete="off"
            placeholder="name@company.com"
            value={to}
            onChange={(e) => setTo(e.target.value)}
            className="mt-1 h-10 w-full rounded-md border border-rule-strong bg-sheet px-3 text-[15px] text-ink placeholder:text-ink-3 focus-visible:border-brand focus-visible:outline-none"
          />
          {error && <p className="mt-3 text-sm text-negative">{error}</p>}
          {view && (
            <>
              <p className="mt-5 text-sm text-ink-3">Subject</p>
              <p className="text-[15px] font-medium text-ink">{view.subject}</p>
              <p className="mt-4 text-sm text-ink-3">Message</p>
              <p className="prose-serif mt-1 text-[15px] whitespace-pre-line text-ink">{view.body}</p>
              <p className="meta num mt-2">
                {view.words} words · the one-page PDF is attached in the .eml
                {view.mailto_shortened ? ' · shortened for the Mail app link' : ''}
              </p>
            </>
          )}
        </div>
        {view && (
          <div className="flex flex-wrap gap-2 border-t border-rule p-5">
            <a href={view.gmail_url} target="_blank" rel="noreferrer noopener" className={link}>
              <ExternalLink className="size-4" strokeWidth={1.5} aria-hidden="true" />
              Open in Gmail<span className="sr-only"> (opens in a new tab)</span>
            </a>
            <a href={view.mailto_url} className={link}>
              Open in Mail app
            </a>
            <Button
              variant="outline"
              onClick={async () => {
                if (await copyText(`Subject: ${view.subject}\n\n${view.body}`)) {
                  setCopied(true)
                  window.setTimeout(() => setCopied(false), 1800)
                } else notify({ tone: 'error', title: "Couldn't copy", description: 'Your browser blocked clipboard access.' })
              }}
            >
              {copied ? <Check strokeWidth={1.5} aria-hidden="true" /> : <Copy strokeWidth={1.5} aria-hidden="true" />}
              {copied ? 'Copied' : 'Copy'}
            </Button>
            <a href={STATIC ? exportUrl(slug, 'eml') : `${exportUrl(slug, 'eml')}?to=${encodeURIComponent(to)}`} download className={link}>
              <Download className="size-4" strokeWidth={1.5} aria-hidden="true" />
              {STATIC ? '.eml with PDF (no recipient)' : '.eml with PDF'}
            </a>
          </div>
        )}
      </div>
    </div>
  )
}
