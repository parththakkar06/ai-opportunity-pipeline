import { createContext, useContext, useId, useMemo, useRef, useState, type ReactNode } from 'react'

import { shortDate } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { AssessmentReport, Citation, TraceNode } from '@/types'

// Citations and the evidence trace are built in Python (agents/trace.py); this only renders them.
type Ctx = { nodes: Map<string, TraceNode>; citations: Map<number, Citation>; uncited: Set<string> }
const CitationContext = createContext<Ctx | null>(null)

export function CitationProvider({ report, children }: { report: AssessmentReport; children: ReactNode }) {
  const value = useMemo<Ctx>(
    () => ({
      nodes: new Map((report.trace?.nodes ?? []).map((n) => [n.id, n])),
      citations: new Map((report.citations ?? []).map((c) => [c.n, c])),
      uncited: new Set(report.trace?.uncited ?? []),
    }),
    [report],
  )
  return <CitationContext.Provider value={value}>{children}</CitationContext.Provider>
}

// Once one source popover has been shown, neighbours open instantly (no hover delay).
let lastShown = 0

/** Superscript [n] marks for a trace node (by id) or for explicit citation numbers. */
export function Cite({ id, nums, facts }: { id?: string; nums?: number[]; facts?: string[] }) {
  const ctx = useContext(CitationContext)
  if (!ctx) return null
  const node = id ? ctx.nodes.get(id) : undefined
  const list = nums ?? node?.citations ?? []
  if (!list.length) {
    return id && ctx.uncited.has(id) ? (
      <sup className="ml-0.5 text-[0.7em] font-medium text-caution" title="No source was found for this line">
        [no source]
      </sup>
    ) : null
  }
  return (
    <sup className="ml-0.5 inline-flex gap-px align-super leading-none">
      {list.map((n) => {
        const c = ctx.citations.get(n)
        return c ? <CiteMark key={n} c={c} facts={facts ?? node?.facts ?? []} /> : null
      })}
    </sup>
  )
}

function CiteMark({ c, facts }: { c: Citation; facts: string[] }) {
  const tipId = useId()
  const [open, setOpen] = useState(false)
  const timer = useRef<number | undefined>(undefined)
  const own = facts.filter((f) => f === c.source_id || f.startsWith(`${c.source_id}.`))
  const show = (instant: boolean) => {
    window.clearTimeout(timer.current)
    const delay = instant || Date.now() - lastShown < 800 ? 0 : 300
    timer.current = window.setTimeout(() => {
      lastShown = Date.now()
      setOpen(true)
    }, delay)
  }
  const hide = () => {
    window.clearTimeout(timer.current)
    lastShown = Date.now()
    setOpen(false)
  }
  return (
    <span className="relative inline-block" onMouseEnter={() => show(false)} onMouseLeave={hide}>
      <a
        href={c.url}
        target="_blank"
        rel="noreferrer noopener"
        aria-describedby={tipId}
        onFocus={() => show(true)}
        onBlur={hide}
        className="num rounded-[2px] px-px font-sans text-[0.7em] font-semibold text-brand no-underline hover:underline"
      >
        [{c.n}]
      </a>
      <span
        id={tipId}
        role="tooltip"
        className={cn(
          'absolute bottom-full left-1/2 z-30 mb-1.5 w-72 -translate-x-1/2 rounded-md border border-rule bg-sheet p-3 text-left font-sans text-xs leading-snug font-normal text-ink-2 shadow-float print:hidden',
          open ? 'float-in [--origin:bottom_center]' : 'sr-only',
        )}
      >
        <span className="block text-[13px] font-medium text-ink">{c.title || c.url}</span>
        <span className="meta mt-1 block">
          {c.source_type || 'source'}
          {c.date ? ` · ${shortDate(c.date)}` : ''} · {c.source_id}
          {own.length ? ` · ${own.join(', ')}` : ''}
        </span>
        <span className="mt-1 block truncate text-brand">{c.url.replace(/^https?:\/\//, '')}</span>
      </span>
    </span>
  )
}

/** Pick a pitch line and see the chain behind it: facts → challenges → opportunities → the line. */
export function TracePanel({ report }: { report: AssessmentReport }) {
  const trace = report.trace
  const pitch = useMemo(() => (trace?.nodes ?? []).filter((n) => n.kind === 'pitch'), [trace])
  const [selected, setSelected] = useState<string | null>(pitch[0]?.id ?? null)
  const chain = useMemo(() => {
    if (!trace || !selected) return [] as TraceNode[]
    const parents = new Map<string, string[]>()
    for (const e of trace.edges) parents.set(e.target, [...(parents.get(e.target) ?? []), e.source])
    const seen = new Set<string>()
    const stack = [selected]
    while (stack.length) {
      const id = stack.pop()!
      if (seen.has(id)) continue
      seen.add(id)
      stack.push(...(parents.get(id) ?? []))
    }
    return trace.nodes.filter((n) => seen.has(n.id) && n.id !== selected)
  }, [trace, selected])
  if (!trace || !pitch.length) return null

  const groups: { kind: TraceNode['kind']; label: string }[] = [
    { kind: 'opportunity', label: 'AI opportunities' },
    { kind: 'challenge', label: 'Challenges' },
    { kind: 'fact', label: 'Facts' },
  ]
  return (
    <section aria-labelledby="trace-heading" className="print:hidden">
      <h3 id="trace-heading" className="heading text-lg text-ink">
        Trace
      </h3>
      <p className="meta mt-1">Pick a line from the pitch to see the evidence behind it.</p>
      <ul className="mt-3 space-y-1" aria-label="Pitch lines">
        {pitch.map((n) => (
          <li key={n.id}>
            <button
              type="button"
              aria-pressed={selected === n.id}
              onClick={() => setSelected(n.id)}
              className={cn(
                'w-full border-l-2 py-1.5 pr-2 pl-3 text-left text-[13px] leading-snug',
                selected === n.id ? 'border-brand bg-tint text-ink' : 'border-rule text-ink-2 hover:border-rule-strong hover:text-ink',
              )}
            >
              <span className="line-clamp-2">{n.label}</span>
              {trace.uncited.includes(n.id) && <span className="mt-0.5 block text-xs text-caution">No source found</span>}
            </button>
          </li>
        ))}
      </ul>
      <div aria-live="polite" className="mt-5 space-y-4">
        {chain.length === 0 && <p className="meta">No linked evidence for this line.</p>}
        {groups.map(({ kind, label }) => {
          const items = chain.filter((n) => n.kind === kind)
          if (!items.length) return null
          return (
            <div key={kind}>
              <p className="meta">{label}</p>
              <ul className="mt-1 space-y-1">
                {items.map((n) => (
                  <li key={n.id} className="text-[13px] leading-snug text-ink-2 [overflow-wrap:anywhere]">
                    <span className="num font-mono text-[11px] text-ink-3">{n.id}</span> {n.label}
                    <Cite id={n.id} />
                  </li>
                ))}
              </ul>
            </div>
          )
        })}
      </div>
    </section>
  )
}
