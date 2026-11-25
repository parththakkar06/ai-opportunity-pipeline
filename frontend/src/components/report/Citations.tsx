import { createContext, useContext, useId, useMemo, useState, type ReactNode } from 'react'
import type { AssessmentReport, Citation, TraceNode } from '../../types'
import { Card, cx } from '../ui'

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

/** Superscript [n] markers for one claim; each shows its source on hover or keyboard focus. */
export function Cite({ id }: { id: string }) {
  const ctx = useContext(CitationContext)
  if (!ctx) return null
  const node = ctx.nodes.get(id)
  if (!node?.citations.length) {
    return ctx.uncited.has(id) ? (
      <sup className="ml-0.5 text-xs font-medium text-warning-foreground" title="No source found for this line">
        [no source]
      </sup>
    ) : null
  }
  return (
    <sup className="ml-0.5 inline-flex gap-0.5 align-super">
      {node.citations.map((n) => {
        const c = ctx.citations.get(n)
        return c ? <CiteMark key={n} c={c} facts={node.facts} /> : null
      })}
    </sup>
  )
}

function CiteMark({ c, facts }: { c: Citation; facts: string[] }) {
  const tipId = useId()
  const own = facts.filter((f) => f === c.source_id || f.startsWith(`${c.source_id}.`))
  return (
    <span className="group relative inline-block">
      <a
        href={c.url}
        target="_blank"
        rel="noreferrer"
        aria-describedby={tipId}
        className="rounded px-0.5 text-xs font-semibold text-accent no-underline hover:underline focus-visible:outline-2 focus-visible:outline-accent"
      >
        [{c.n}]
      </a>
      <span
        id={tipId}
        role="tooltip"
        className="pointer-events-none invisible absolute bottom-full left-1/2 z-30 mb-1 w-64 -translate-x-1/2 rounded-lg border border-border bg-card p-3 text-left text-xs leading-snug font-normal text-secondary opacity-0 shadow-lg transition-opacity duration-150 group-focus-within:visible group-focus-within:opacity-100 group-hover:visible group-hover:opacity-100 print:hidden"
      >
        <span className="block font-semibold text-foreground">{c.title || c.url}</span>
        <span className="mt-1 block text-muted-foreground">
          {c.source_type || 'source'}
          {c.date ? ` · ${c.date}` : ''} · {c.source_id}
          {own.length ? ` · facts ${own.join(', ')}` : ''}
        </span>
        <span className="mt-1 block truncate text-accent">{c.url}</span>
      </span>
    </span>
  )
}

/** Pick a pitch line and see the chain behind it: facts -> challenges -> opportunities -> the line. */
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
    <Card className="mx-auto max-w-[46rem] p-5 sm:p-6 print:hidden">
      <h3 className="text-sm font-semibold tracking-wide text-muted-foreground uppercase">Trace</h3>
      <p className="mt-1 text-sm text-muted-foreground">Pick a line from the pitch to see the evidence chain behind it.</p>
      <div className="mt-4 grid gap-5 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <ul className="space-y-1.5" aria-label="Pitch lines">
          {pitch.map((n) => (
            <li key={n.id}>
              <button
                type="button"
                aria-pressed={selected === n.id}
                onClick={() => setSelected(n.id)}
                className={cx(
                  'w-full rounded-lg border px-3 py-2 text-left text-sm transition-colors',
                  selected === n.id ? 'border-accent bg-accent/10 text-foreground' : 'border-border text-secondary hover:bg-subtle',
                )}
              >
                <span className="line-clamp-2">{n.label}</span>
                {trace.uncited.includes(n.id) && (
                  <span className="mt-1 block text-xs font-medium text-warning-foreground">No source found</span>
                )}
              </button>
            </li>
          ))}
        </ul>
        <div aria-live="polite" className="space-y-4">
          {chain.length === 0 && <p className="text-sm text-muted-foreground">No linked evidence for this line.</p>}
          {groups.map(({ kind, label }) => {
            const items = chain.filter((n) => n.kind === kind)
            if (!items.length) return null
            return (
              <div key={kind}>
                <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">{label}</p>
                <ul className="mt-1.5 space-y-1.5">
                  {items.map((n) => (
                    <li key={n.id} className="text-sm text-secondary">
                      <span className="font-mono text-xs text-muted-foreground">{n.id}</span> {n.label}
                      <Cite id={n.id} />
                    </li>
                  ))}
                </ul>
              </div>
            )
          })}
        </div>
      </div>
    </Card>
  )
}
