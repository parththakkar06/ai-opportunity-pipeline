import { AnimatePresence, m, useReducedMotion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { duration, ease, fadeRise } from '../../lib/motion'
import { useNow } from '../../lib/useNow'
import { AlertIcon, Badge, Button, Card, CheckIcon, Label, ResumeIcon, Spinner, cx } from '../ui'
import {
  STAGES,
  firstUnfinishedStage,
  formatDuration,
  isWarningNote,
  type AgentResult,
  type RunState,
  type StageProgress,
} from './progress'

interface Props {
  run: RunState
  onStop: () => void
  onResume: (fromStage: number) => void
  onDismiss: () => void
}

/** The main workspace while an analysis runs, and afterwards if it failed or was stopped. */
export function RunView({ run, onStop, onResume, onDismiss }: Props) {
  const now = useNow(run.running)
  const elapsed = (run.finishedAt ?? now) - run.startedAt
  const finished = STAGES.filter((s) => ['done', 'skipped'].includes(run.progress[s.id].state)).length
  const active = STAGES.find((s) => run.progress[s.id].state === 'active')
  const failed = STAGES.find((s) => run.progress[s.id].state === 'error')
  const fraction = Math.min(1, (finished + (active ? 0.5 : 0)) / STAGES.length)
  const resumeFrom = firstUnfinishedStage(run.progress)
  const announcement = useStageAnnouncement(run)

  // Take focus whenever a new run (or a resume) starts, including the first time this lazy view loads.
  useEffect(() => {
    const frame = requestAnimationFrame(() => document.getElementById('run-title')?.focus())
    return () => cancelAnimationFrame(frame)
  }, [run.startedAt])

  return (
    <div className="space-y-5">
      <p className="sr-only" aria-live="polite" aria-atomic="true">
        {announcement}
      </p>

      <Card className="overflow-hidden">
        <div className="p-6 sm:p-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-widest text-accent">
                {run.running ? 'Analysis in progress' : run.error ? 'Analysis stopped' : 'Analysis complete'}
              </p>
              <h1 id="run-title" tabIndex={-1} className="mt-1 text-2xl font-bold text-foreground focus:outline-none sm:text-3xl">
                {run.company}
              </h1>
              {run.url && <p className="mt-1 text-base text-muted-foreground">{run.url}</p>}
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              {run.running ? (
                <Button onClick={onStop}>Stop</Button>
              ) : (
                <>
                  {run.error && resumeFrom && resumeFrom > 1 && (
                    <Button variant="primary" onClick={() => onResume(resumeFrom)}>
                      <ResumeIcon className="h-4 w-4" />
                      Resume from stage {resumeFrom}
                    </Button>
                  )}
                  <Button variant="ghost" onClick={onDismiss}>
                    Close
                  </Button>
                </>
              )}
            </div>
          </div>

          <dl className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Stat label="Elapsed" value={formatDuration(elapsed)} mono />
            <Stat label="Stages" value={`${finished} of ${STAGES.length}`} mono />
            <Stat label="Model" value={run.model ?? '…'} title={run.model} />
            <Stat label="Search" value={run.searchChain?.join(' → ') ?? '…'} />
          </dl>
        </div>

        <div
          className="h-1.5 bg-muted"
          role="progressbar"
          aria-label="Overall progress"
          aria-valuemin={0}
          aria-valuemax={STAGES.length}
          aria-valuenow={finished}
          aria-valuetext={`${finished} of ${STAGES.length} stages complete`}
        >
          <m.div
            className={cx('h-full origin-left', run.error ? 'bg-danger' : 'bg-accent')}
            initial={false}
            animate={{ scaleX: fraction }}
            transition={{ duration: duration.slow, ease: ease.out }}
          />
        </div>
      </Card>

      <AnimatePresence initial={false}>
        {run.error && (
          <m.div variants={fadeRise} initial="initial" animate="animate" exit="exit">
            <div className="flex gap-3 rounded-2xl bg-danger-soft p-4 text-danger-foreground ring-1 ring-danger/30" role="alert">
              <AlertIcon className="mt-0.5 h-5 w-5 shrink-0" />
              <div className="min-w-0 text-sm">
                <p className="font-semibold">
                  The analysis stopped{failed ? ` during stage ${failed.id}, ${failed.title}` : ''}.
                </p>
                <p className="mt-1 [overflow-wrap:anywhere]">{run.error}</p>
                {resumeFrom && resumeFrom > 1 && (
                  <p className="mt-2 text-secondary">
                    Stages 1–{resumeFrom - 1} are saved. Resuming reuses them, so no requests are spent redoing them.
                  </p>
                )}
              </div>
            </div>
          </m.div>
        )}
      </AnimatePresence>

      <Card className="p-4 sm:p-6">
        <h2 className="sr-only">Stages</h2>
        <ol className="space-y-0">
          {STAGES.map((stage, i) => (
            <StageRow
              key={stage.id}
              index={stage.id}
              title={stage.title}
              blurb={stage.blurb}
              progress={run.progress[stage.id]}
              agents={run.agents.filter((a) => a.stage === stage.id)}
              isLast={i === STAGES.length - 1}
              now={now}
            />
          ))}
        </ol>
      </Card>

      <UsageSummary agents={run.agents} />
    </div>
  )
}

function Stat({ label, value, mono, title }: { label: string; value: string; mono?: boolean; title?: string }) {
  return (
    <div className="min-w-0">
      <dt>
        <Label>{label}</Label>
      </dt>
      <dd
        className={cx('mt-1 truncate text-base font-semibold text-foreground', mono && 'tabular-nums')}
        title={title ?? value}
      >
        {value}
      </dd>
    </div>
  )
}

const MAX_NOTES = 4

function StageRow({
  index,
  title,
  blurb,
  progress: p,
  agents,
  isLast,
  now,
}: {
  index: number
  title: string
  blurb: string
  progress: StageProgress
  agents: AgentResult[]
  isLast: boolean
  now: number
}) {
  const [showAllNotes, setShowAllNotes] = useState(false)
  const done = p.state === 'done' || p.state === 'skipped'
  const notes = showAllNotes ? p.notes : p.notes.slice(-MAX_NOTES)
  const hidden = p.notes.length - notes.length

  return (
    <li className="relative flex gap-4 pb-6 last:pb-0" aria-current={p.state === 'active' ? 'step' : undefined}>
      {!isLast && (
        <span className="absolute top-11 bottom-1 left-[19px] w-0.5 bg-border" aria-hidden="true">
          <m.span
            className="block h-full w-full origin-top bg-accent"
            initial={false}
            animate={{ scaleY: done ? 1 : 0 }}
            transition={{ duration: duration.slow, ease: ease.out }}
          />
        </span>
      )}
      <StageDot state={p.state} index={index} />
      <div className="min-w-0 flex-1 pt-1.5">
        <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
          <h3 className={cx('text-base font-semibold', p.state === 'pending' ? 'text-muted-foreground' : 'text-foreground')}>
            <span className="sr-only">Stage {index}: </span>
            {title}
          </h3>
          <StateChip progress={p} now={now} />
        </div>
        <p className="mt-0.5 text-sm text-muted-foreground">
          {p.state === 'active' && p.message ? (
            <span className="text-secondary">{p.message}…</span>
          ) : (
            blurb
          )}
        </p>

        {agents.length > 0 && (
          <ul className="mt-2 space-y-1">
            {agents.map((a) => (
              <li key={a.agent} className="flex flex-wrap items-center gap-x-2 text-sm text-muted-foreground">
                <CheckIcon className="h-3.5 w-3.5 text-success" />
                <span className="font-medium text-secondary">{a.agent}</span>
                <span className="tabular-nums">
                  {a.seconds.toFixed(0)}s · {(a.inputTokens + a.outputTokens).toLocaleString()} tokens · {a.cost}
                </span>
              </li>
            ))}
          </ul>
        )}

        {p.notes.length > 0 && (
          <ul className="mt-2.5 space-y-1.5 rounded-xl bg-subtle p-3">
            <AnimatePresence initial={false}>
              {notes.map((note, j) => (
                <m.li
                  key={`${p.notes.length - notes.length + j}-${note}`}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0, transition: { duration: duration.base, ease: ease.out } }}
                  className={cx(
                    'flex gap-2 text-sm [overflow-wrap:anywhere]',
                    isWarningNote(note) ? 'text-warning-foreground' : 'text-secondary',
                  )}
                >
                  <span aria-hidden="true" className="shrink-0">
                    {isWarningNote(note) ? '!' : '›'}
                  </span>
                  <span>{note}</span>
                </m.li>
              ))}
            </AnimatePresence>
            {(hidden > 0 || showAllNotes) && p.notes.length > MAX_NOTES && (
              <li>
                <button
                  type="button"
                  onClick={() => setShowAllNotes((v) => !v)}
                  className="text-sm font-medium text-accent hover:underline"
                >
                  {showAllNotes ? 'Show fewer' : `Show ${hidden} earlier note${hidden === 1 ? '' : 's'}`}
                </button>
              </li>
            )}
          </ul>
        )}
      </div>
    </li>
  )
}

function StateChip({ progress: p, now }: { progress: StageProgress; now: number }) {
  switch (p.state) {
    case 'active':
      return (
        <Badge tone="indigo">
          <Spinner className="h-3 w-3" /> Running
          {p.startedAt && <span className="tabular-nums">· {formatDuration(now - p.startedAt)}</span>}
        </Badge>
      )
    case 'done':
      return (
        <Badge tone="green">
          <CheckIcon className="h-3 w-3" /> Done{p.seconds !== undefined && ` · ${formatDuration(p.seconds * 1000)}`}
        </Badge>
      )
    case 'skipped':
      return <Badge>Reused saved result</Badge>
    case 'error':
      return (
        <Badge tone="red">
          <AlertIcon className="h-3 w-3" /> Failed
        </Badge>
      )
    default:
      return <Badge>Waiting</Badge>
  }
}

function StageDot({ state, index }: { state: StageProgress['state']; index: number }) {
  // The pulse is decorative: under "reduce motion" it's replaced by a static ring (an opacity loop
  // would otherwise keep running, since reducedMotion="user" only removes transform animations).
  const reduceMotion = useReducedMotion()
  const base = 'relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-bold'
  if (state === 'done' || state === 'skipped')
    return (
      <span className={cx(base, 'bg-accent text-on-accent')}>
        <CheckIcon className="h-5 w-5" />
      </span>
    )
  if (state === 'error')
    return (
      <span className={cx(base, 'bg-danger-soft text-danger-foreground ring-2 ring-danger')}>
        <AlertIcon className="h-5 w-5" />
      </span>
    )
  if (state === 'active')
    return (
      <span className={cx(base, 'bg-accent-soft text-accent ring-2 ring-accent')}>
        {reduceMotion ? (
          <span className="absolute -inset-1 rounded-full ring-2 ring-accent/40" aria-hidden="true" />
        ) : (
          <m.span
            className="absolute inset-0 rounded-full ring-2 ring-accent"
            aria-hidden="true"
            animate={{ opacity: [0.6, 0], scale: [1, 1.35] }}
            transition={{ duration: 1.6, repeat: Infinity, ease: 'easeOut' }}
          />
        )}
        {index}
      </span>
    )
  return <span className={cx(base, 'bg-card text-muted-foreground ring-1 ring-border-strong')}>{index}</span>
}

function UsageSummary({ agents }: { agents: AgentResult[] }) {
  if (agents.length === 0) return null
  const tokens = agents.reduce((n, a) => n + a.inputTokens + a.outputTokens, 0)
  const costs = agents.map((a) => a.cost)
  const cost = costs.some((c) => c === 'n/a')
    ? 'n/a'
    : `$${costs.reduce((n, c) => n + Number(c.replace(/[$,]/g, '')), 0).toFixed(4)}`
  return (
    <p className="text-center text-sm text-muted-foreground tabular-nums">
      So far: {agents.length} agent{agents.length === 1 ? '' : 's'} finished · {tokens.toLocaleString()} tokens · cost {cost}
    </p>
  )
}

/** Turns stage transitions into one short sentence for screen readers. */
function useStageAnnouncement(run: RunState): string {
  const previous = useRef<Record<number, string>>({})
  const [message, setMessage] = useState('')
  useEffect(() => {
    for (const s of STAGES) {
      const state = run.progress[s.id].state
      if (previous.current[s.id] === state) continue
      previous.current[s.id] = state
      if (state === 'active') setMessage(`Stage ${s.id} of 4, ${s.title}, started.`)
      else if (state === 'done') setMessage(`Stage ${s.id}, ${s.title}, finished.`)
      else if (state === 'error') setMessage(`Stage ${s.id}, ${s.title}, failed.`)
    }
  }, [run.progress])
  return message
}
