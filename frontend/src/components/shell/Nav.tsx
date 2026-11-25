import { Info, Search } from 'lucide-react'
import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { compact, relativeTime } from '@/lib/format'
import { STATIC } from '@/lib/static'
import { cn } from '@/lib/utils'
import type { Health, RunMeta, SavedRun } from '@/types'

import { ThemeToggle } from './ThemeToggle'

const STAGE_NAMES: Record<string, string> = { '1': 'Research', '2': 'Challenges', '3': 'Opportunities', '4': 'Pitch' }

export function Nav({
  showCommandBar,
  runs,
  running,
  onHome,
  onOpenRun,
  onAnalyze,
  onHowItWorks,
  actions,
}: {
  showCommandBar: boolean
  runs: SavedRun[]
  running: boolean
  onHome: () => void
  onOpenRun: (slug: string) => void
  onAnalyze: (company: string) => void
  onHowItWorks: () => void
  actions?: ReactNode
}) {
  return (
    <header className="no-print sticky top-0 z-20 border-b border-rule bg-paper/95 backdrop-blur-sm">
      <div className="mx-auto flex h-14 max-w-[1320px] items-center gap-2 px-4 sm:gap-3 sm:px-6">
        <a
          href="/"
          onClick={(e) => {
            e.preventDefault()
            onHome()
          }}
          className="heading shrink-0 text-[1.0625rem] text-ink sm:text-xl"
          translate="no"
        >
          AI Opportunity Studio
        </a>
        <div className="min-w-0 flex-1">
          {showCommandBar && (
            <CommandBar runs={runs} running={running} onOpenRun={onOpenRun} onAnalyze={onAnalyze} onHome={onHome} />
          )}
        </div>
        <nav aria-label="App" className="flex shrink-0 items-center gap-0.5 sm:gap-1">
          <Button variant="ghost" size="sm" onClick={onHowItWorks} className="hidden md:inline-flex">
            How it works
          </Button>
          {actions}
          <ThemeToggle />
        </nav>
      </div>
    </header>
  )
}

/** "Research another company…": `/` focuses it, typing filters saved reports, Enter opens or runs. */
function CommandBar({
  runs,
  running,
  onOpenRun,
  onAnalyze,
  onHome,
}: {
  runs: SavedRun[]
  running: boolean
  onOpenRun: (slug: string) => void
  onAnalyze: (company: string) => void
  onHome: () => void
}) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const inputRef = useRef<HTMLInputElement>(null)
  const listId = useId()

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      if (e.key === '/' && !/input|textarea|select/i.test(target.tagName) && !target.isContentEditable) {
        e.preventDefault()
        inputRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const q = query.trim().toLowerCase()
  const matches = useMemo(
    () => (q ? runs.filter((r) => r.business_name.toLowerCase().includes(q) || r.slug.includes(q)).slice(0, 6) : []),
    [runs, q],
  )
  const options = [...matches.map((r) => ({ kind: 'open' as const, run: r })), ...(q && !STATIC ? [{ kind: 'new' as const }] : [])]

  const choose = (i: number) => {
    const opt = options[i]
    if (!opt) return
    if (opt.kind === 'open') onOpenRun(opt.run.slug)
    else if (!running) onAnalyze(query.trim())
    setQuery('')
    setOpen(false)
    inputRef.current?.blur()
  }

  return (
    <>
      <div className="relative mx-auto hidden w-full max-w-md sm:block">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-ink-3" strokeWidth={1.5} aria-hidden="true" />
        <input
          ref={inputRef}
          type="text"
          role="combobox"
          aria-label={STATIC ? 'Open a report' : 'Research another company or open a saved report'}
          aria-expanded={open && options.length > 0}
          aria-controls={listId}
          aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}
          aria-autocomplete="list"
          autoComplete="off"
          spellCheck={false}
          placeholder={STATIC ? 'Open a report…' : 'Research another company…'}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setOpen(true)
            setActive(-1)
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => window.setTimeout(() => setOpen(false), 120)}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') {
              e.preventDefault()
              setOpen(true)
              setActive((a) => Math.min(options.length - 1, a + 1))
            } else if (e.key === 'ArrowUp') {
              e.preventDefault()
              setActive((a) => Math.max(-1, a - 1))
            } else if (e.key === 'Enter' && q) {
              e.preventDefault()
              choose(active >= 0 ? active : options.length - 1)
            } else if (e.key === 'Escape') {
              setQuery('')
              setOpen(false)
              inputRef.current?.blur()
            }
          }}
          className="h-9 w-full rounded-md border border-rule bg-sheet pr-8 pl-8 text-sm text-ink placeholder:text-ink-3 focus-visible:border-brand focus-visible:outline-none"
        />
        <kbd className="pointer-events-none absolute top-1/2 right-2 -translate-y-1/2 rounded-[3px] border border-rule px-1.5 font-sans text-[11px] text-ink-3">
          /
        </kbd>
        {open && options.length > 0 && (
          <ul
            id={listId}
            role="listbox"
            aria-label="Suggestions"
            className="absolute top-full right-0 left-0 z-30 mt-1.5 rounded-md border border-rule bg-sheet p-1 shadow-float"
          >
            {options.map((opt, i) => (
              <li
                key={opt.kind === 'open' ? opt.run.slug : 'new'}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === active}
                onMouseDown={(e) => {
                  e.preventDefault()
                  choose(i)
                }}
                onMouseEnter={() => setActive(i)}
                className={cn('flex cursor-pointer items-baseline justify-between gap-3 rounded-[3px] px-2.5 py-1.5 text-sm', i === active && 'bg-tint')}
              >
                {opt.kind === 'open' ? (
                  <>
                    <span className="truncate text-ink">{opt.run.business_name}</span>
                    <span className="meta shrink-0">Saved · {relativeTime(opt.run.generated_at)}</span>
                  </>
                ) : (
                  <span className="text-ink">
                    {running ? 'A run is in progress' : <>Research “{query.trim()}”</>}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
      <Button variant="ghost" size="icon" className="sm:hidden" onClick={onHome} aria-label="New research">
        <Search strokeWidth={1.5} aria-hidden="true" />
      </Button>
    </>
  )
}

/** Provider, models, tokens per stage and research stats, out of the way of the report itself. */
export function RunDetails({ meta, health }: { meta?: RunMeta | null; health: Health | null }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const id = useId()
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

  const stages = Object.entries(meta?.stages ?? {})
  const research = meta?.research ?? {}
  return (
    <div ref={ref} className="relative">
      <Button variant="ghost" size="sm" aria-expanded={open} aria-controls={id} onClick={() => setOpen((v) => !v)}>
        <Info strokeWidth={1.5} aria-hidden="true" />
        <span className="hidden lg:inline">Run details</span>
        <span className="sr-only lg:hidden">Run details</span>
      </Button>
      {open && (
        <div
          id={id}
          role="dialog"
          aria-label="Run details"
          className="float-in absolute right-0 z-30 mt-1.5 w-[min(22rem,calc(100vw-2rem))] rounded-md border border-rule bg-sheet p-4 text-sm shadow-float"
        >
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
            <dt className="meta">Provider</dt>
            <dd className="text-ink">{meta?.provider ?? health?.provider ?? '—'}</dd>
            <dt className="meta">Model</dt>
            <dd className="break-all text-ink">{meta?.model ?? health?.model ?? '—'}</dd>
            {meta?.builder_model && meta.builder_model !== meta.model && (
              <>
                <dt className="meta">Pitch model</dt>
                <dd className="break-all text-ink">{meta.builder_model}</dd>
              </>
            )}
            <dt className="meta">Search</dt>
            <dd className="text-ink">{meta?.search_providers_used?.join(', ') || health?.search_provider || '—'}</dd>
            {meta?.elapsed_seconds != null && (
              <>
                <dt className="meta">Time</dt>
                <dd className="num text-ink">{Math.round(meta.elapsed_seconds)} s</dd>
              </>
            )}
            {research.documents != null && (
              <>
                <dt className="meta">Sources read</dt>
                <dd className="num text-ink">
                  {String(research.documents)} documents · {String(research.facts ?? 0)} facts
                  {research.cache_hits ? ` · ${String(research.cache_hits)} cached` : ''}
                </dd>
              </>
            )}
          </dl>
          {stages.length > 0 ? (
            <table className="num mt-3 w-full border-t border-rule text-[13px]">
              <caption className="sr-only">Tokens per stage</caption>
              <thead>
                <tr className="text-left text-ink-3">
                  <th scope="col" className="py-1.5 font-normal">Stage</th>
                  <th scope="col" className="py-1.5 text-right font-normal">In</th>
                  <th scope="col" className="py-1.5 text-right font-normal">Out</th>
                  <th scope="col" className="py-1.5 text-right font-normal">Calls</th>
                </tr>
              </thead>
              <tbody>
                {stages.map(([k, s]) => (
                  <tr key={k} className="border-t border-rule">
                    <th scope="row" className="py-1 text-left font-normal text-ink">{STAGE_NAMES[k] ?? `Stage ${k}`}</th>
                    <td className="py-1 text-right">{compact(s.input_tokens)}</td>
                    <td className="py-1 text-right">{compact(s.output_tokens)}</td>
                    <td className="py-1 text-right">{s.calls ?? '—'}</td>
                  </tr>
                ))}
                <tr className="border-t border-rule-strong font-medium">
                  <th scope="row" className="py-1 text-left">Total</th>
                  <td className="py-1 text-right">{compact(meta?.total_input_tokens)}</td>
                  <td className="py-1 text-right">{compact(meta?.total_output_tokens)}</td>
                  <td className="py-1 text-right">{stages.reduce((n, [, s]) => n + (s.calls ?? 0), 0)}</td>
                </tr>
              </tbody>
            </table>
          ) : (
            <p className="meta mt-3 border-t border-rule pt-3">
              {meta ? 'This run was saved before per-stage token logging.' : 'No run details for this report.'}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
