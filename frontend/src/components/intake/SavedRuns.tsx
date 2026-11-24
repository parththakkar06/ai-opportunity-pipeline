import { useId, useMemo, useState } from 'react'
import { relativeTime } from '../../lib/format'
import type { SavedRun } from '../../types'
import { Badge, Card, CircleCheckIcon, HalfCircleIcon, ResumeIcon, SearchIcon, Spinner, cx, qualityTone } from '../ui'

interface Props {
  runs: SavedRun[]
  loading: boolean
  selectedSlug: string | null
  running: boolean
  onOpen: (slug: string) => void
  onResume: (run: SavedRun) => void
}

export function SavedRuns({ runs, loading, selectedSlug, running, onOpen, onResume }: Props) {
  const searchId = useId()
  const headingId = useId()
  const [query, setQuery] = useState('')
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return runs
    return runs.filter((r) =>
      [r.business_name, r.input_name, r.industry, r.slug].some((v) => v?.toLowerCase().includes(q)),
    )
  }, [runs, query])

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between gap-2">
        <h2 id={headingId} className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Saved reports {runs.length > 0 && <span className="font-normal">({runs.length})</span>}
        </h2>
        {loading && <Spinner className="h-4 w-4 text-muted-foreground" />}
      </div>

      {runs.length > 3 && (
        <div className="relative mt-3">
          <label htmlFor={searchId} className="sr-only">
            Search saved reports
          </label>
          <SearchIcon className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            id={searchId}
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by company or industry"
            className="w-full rounded-lg border border-border-strong bg-card py-2.5 pr-3 pl-9 text-base text-foreground placeholder:text-muted-foreground sm:text-sm"
          />
        </div>
      )}

      {runs.length === 0 && !loading ? (
        <p className="mt-3 text-sm text-muted-foreground">
          No saved reports yet. Finished and partial runs from <code className="font-mono">outputs/</code> appear here.
        </p>
      ) : filtered.length === 0 ? (
        <p className="mt-3 text-sm text-muted-foreground">No reports match “{query}”.</p>
      ) : (
        <ul className="mt-3 space-y-1.5" aria-labelledby={headingId}>
          {filtered.map((r) => {
            const selected = selectedSlug === r.slug
            return (
              <li
                key={r.slug}
                className={cx(
                  'flex items-stretch gap-1 rounded-xl ring-1 ring-inset transition-colors duration-150',
                  selected ? 'bg-accent-soft ring-accent/40' : 'ring-transparent hover:bg-subtle',
                )}
              >
                <button
                  type="button"
                  onClick={() => onOpen(r.slug)}
                  disabled={running}
                  aria-current={selected ? 'true' : undefined}
                  className="flex min-h-11 min-w-0 flex-1 items-center gap-3 rounded-xl px-2.5 py-2 text-left disabled:opacity-50"
                >
                  <StatusIcon run={r} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold text-foreground">{r.business_name}</span>
                    <span className="block truncate text-xs text-muted-foreground">
                      {r.complete ? 'Complete' : `Stages ${r.stages_completed.join(', ')} of 4`}
                      {r.generated_at && ` · ${relativeTime(r.generated_at)}`}
                    </span>
                  </span>
                  <Badge tone={qualityTone(r.data_quality)}>{r.data_quality} data</Badge>
                </button>
                {!r.complete && r.next_stage && (
                  <button
                    type="button"
                    onClick={() => onResume(r)}
                    disabled={running}
                    aria-label={`Resume ${r.business_name} from stage ${r.next_stage}`}
                    title={`Resume from stage ${r.next_stage}`}
                    className="flex min-h-11 min-w-11 items-center justify-center rounded-xl text-accent transition-colors duration-150 hover:bg-accent-soft disabled:opacity-50"
                  >
                    <ResumeIcon className="h-4 w-4" />
                  </button>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}

function StatusIcon({ run }: { run: SavedRun }) {
  return run.complete ? (
    <span className="text-success" title="All 4 stages complete">
      <CircleCheckIcon className="h-5 w-5" />
      <span className="sr-only">Complete.</span>
    </span>
  ) : (
    <span className="text-warning" title="Partial run">
      <HalfCircleIcon className="h-5 w-5" />
      <span className="sr-only">Partial.</span>
    </span>
  )
}
