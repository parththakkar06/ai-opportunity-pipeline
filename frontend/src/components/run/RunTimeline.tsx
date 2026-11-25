import { Check, CircleAlert } from 'lucide-react'
import { useEffect, useRef } from 'react'

import { Button } from '@/components/ui/button'
import { compact } from '@/lib/format'
import { useNow } from '@/lib/useNow'
import { cn } from '@/lib/utils'

import { STAGES, firstUnfinishedStage, formatDuration, isWarningNote, type RunState } from './progress'

const STAGE_NAMES: Record<number, string> = { 1: 'Research', 2: 'Challenges', 3: 'Opportunities', 4: 'Pitch' }

/** A calm vertical timeline: one row per stage with time, sources and tokens; notes stream as log lines. */
export function RunTimeline({
  run,
  onStop,
  onResume,
  onDismiss,
}: {
  run: RunState
  onStop: () => void
  onResume: (fromStage: number) => void
  onDismiss: () => void
}) {
  const now = useNow(run.running)
  const elapsed = (run.finishedAt ?? now) - run.startedAt
  const resumeFrom = firstUnfinishedStage(run.progress)
  const headingRef = useRef<HTMLHeadingElement>(null)
  const announce = useAnnouncer(run)

  useEffect(() => headingRef.current?.focus({ preventScroll: true }), [])

  const tokensFor = (stage: number) =>
    run.agents.filter((a) => a.stage === stage).reduce((n, a) => n + a.inputTokens + a.outputTokens, 0)

  return (
    <div className="mx-auto max-w-[44rem] px-4 pt-14 pb-24 sm:px-6">
      <p className="meta">{run.running ? 'Researching' : run.error ? 'Stopped' : 'Finished'}</p>
      <h1 ref={headingRef} tabIndex={-1} className="display mt-1 text-[2.25rem] text-ink">
        {run.company}
      </h1>
      <p className="meta num mt-2">
        {formatDuration(elapsed)} elapsed
        {run.model && ` · ${run.model}`}
        {run.searchChain?.length ? ` · search: ${run.searchChain.join(' → ')}` : ''}
      </p>

      <div className="mt-5 flex flex-wrap gap-2">
        {run.running ? (
          <Button variant="outline" onClick={onStop}>
            Stop
          </Button>
        ) : (
          <>
            {run.error && resumeFrom && (
              <Button onClick={() => onResume(resumeFrom)}>Resume from stage {resumeFrom}</Button>
            )}
            <Button variant="ghost" onClick={onDismiss}>
              Close
            </Button>
          </>
        )}
      </div>

      {run.error && (
        <div role="alert" className="mt-6 flex gap-2 border-l-2 border-negative py-1 pl-3 text-sm text-ink">
          <CircleAlert className="mt-0.5 size-4 shrink-0 text-negative" strokeWidth={1.5} aria-hidden="true" />
          <p className="[overflow-wrap:anywhere]">
            {run.error} Completed stages are saved on the server
            {resumeFrom && resumeFrom > 1 ? `, so you can resume from stage ${resumeFrom}.` : '.'}
          </p>
        </div>
      )}

      <ol className="mt-10" aria-label="Pipeline stages">
        {STAGES.map((s, i) => {
          const p = run.progress[s.id]
          const live = p.state === 'active'
          const seconds = p.seconds ?? (live && p.startedAt ? (now - p.startedAt) / 1000 : undefined)
          const tokens = tokensFor(s.id)
          const sources = s.id === 1 ? Math.max(0, ...p.notes.map((n) => Number(n.match(/(\d+) documents? read/)?.[1] ?? 0))) : 0
          return (
            <li key={s.id} className="relative grid grid-cols-[1.5rem_minmax(0,1fr)] gap-x-4 pb-8 last:pb-0">
              {i < STAGES.length - 1 && (
                <span aria-hidden="true" className="absolute top-6 bottom-0 left-[0.6875rem] w-px bg-rule" />
              )}
              <StageGlyph state={p.state} />
              <div>
                <div className="flex flex-wrap items-baseline gap-x-3">
                  <h2 className={cn('text-[15px] font-medium', p.state === 'pending' ? 'text-ink-3' : 'text-ink')}>
                    {STAGE_NAMES[s.id]}
                  </h2>
                  <span className="meta num">
                    {p.state === 'skipped'
                      ? 'reused from the saved run'
                      : [
                          seconds != null ? formatDuration(seconds * 1000) : null,
                          sources ? `${sources} sources read` : null,
                          tokens ? `${compact(tokens)} tokens` : null,
                        ]
                          .filter(Boolean)
                          .join(' · ')}
                  </span>
                </div>
                <p className="meta">{s.blurb}</p>
                {live && p.message && <p className="mt-1 text-sm text-ink-2">{p.message}…</p>}
                {p.notes.length > 0 && (
                  <ul className="mt-2 space-y-0.5 font-mono text-[12.5px] leading-relaxed">
                    {p.notes.map((n, j) => (
                      <li key={j} className={cn('rise-in flex gap-2 [overflow-wrap:anywhere]', isWarningNote(n) ? 'text-caution' : 'text-ink-3')}>
                        <span aria-hidden="true">{isWarningNote(n) ? '!' : '›'}</span>
                        {n}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </li>
          )
        })}
      </ol>
      <p className="sr-only" role="status" aria-live="polite">
        {announce}
      </p>
    </div>
  )
}

function StageGlyph({ state }: { state: string }) {
  const base = 'relative z-[1] mt-0.5 flex size-6 items-center justify-center rounded-full bg-paper'
  if (state === 'done' || state === 'skipped')
    return (
      <span className={cn(base, 'border border-ink-2 text-ink')}>
        <Check className="size-3.5" strokeWidth={2} aria-hidden="true" />
        <span className="sr-only">{state === 'done' ? 'Done' : 'Reused'}</span>
      </span>
    )
  if (state === 'active')
    return (
      <span className={cn(base, 'border border-brand')}>
        <span className="size-2 rounded-full bg-brand [animation:pulse-dot_1.6s_ease-in-out_infinite] motion-reduce:animate-none" />
        <span className="sr-only">Running</span>
      </span>
    )
  if (state === 'error')
    return (
      <span className={cn(base, 'border border-negative text-negative')}>
        <CircleAlert className="size-3.5" strokeWidth={2} aria-hidden="true" />
        <span className="sr-only">Failed</span>
      </span>
    )
  return (
    <span className={cn(base, 'border border-rule-strong')}>
      <span className="sr-only">Waiting</span>
    </span>
  )
}

/** One short live-region message per stage change, rather than reading out every log line. */
function useAnnouncer(run: RunState): string {
  const active = STAGES.find((s) => run.progress[s.id].state === 'active')
  const failed = STAGES.find((s) => run.progress[s.id].state === 'error')
  if (failed) return `Stage ${failed.id}, ${STAGE_NAMES[failed.id]}, failed.`
  if (active) return `Stage ${active.id} of 4: ${STAGE_NAMES[active.id]}.`
  return !run.running && !run.error ? 'All stages complete. Opening the report.' : ''
}
