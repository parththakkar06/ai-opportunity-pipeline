import type { StageState, StreamEvent } from '../../types'

export const STAGES = [
  { id: 1, title: 'Researcher', blurb: 'Searches, reads up to 6 pages or PDFs, and extracts dated facts' },
  { id: 2, title: 'Challenge & Reasoning Analyst', blurb: 'Operational, sales and CX challenges with evidence-based reasoning' },
  { id: 3, title: 'AI Opportunity Strategist', blurb: 'Ideas mapped to the challenges, then scored on the rubric' },
  { id: 4, title: 'CEO Pitch Builder', blurb: 'One-page pitch, ROI model, then the verifier checks every claim' },
] as const

export interface StageProgress {
  state: StageState
  message?: string
  notes: string[]
  seconds?: number
  startedAt?: number
}

export type Progress = Record<number, StageProgress>

export interface AgentResult {
  stage: number
  agent: string
  seconds: number
  inputTokens: number
  outputTokens: number
  cost: string
}

export interface RunState {
  company: string
  url: string
  includePrototype: boolean
  runSlug?: string
  fromStage: number
  running: boolean
  progress: Progress
  startedAt: number
  finishedAt?: number
  provider?: string
  model?: string
  searchChain?: string[]
  agents: AgentResult[]
  error?: string
  dismissed?: boolean
}

export const initialProgress = (): Progress =>
  Object.fromEntries(STAGES.map((s) => [s.id, { state: 'pending', notes: [] } satisfies StageProgress]))

/** "baidu/x:free unavailable (rate-limited: …); switching to google/y:free" → "google/y:free". */
export function switchedToModel(note: string): string | null {
  const m = note.match(/switching to (\S+)\s*$/)
  return m ? m[1] : null
}

export const isWarningNote = (note: string) => /unavailable|switching to|failed|issue|limited public information/i.test(note)

/** Pure reducer for stream events, so the run logic stays out of App. */
export function applyEvent(run: RunState, event: StreamEvent): RunState {
  const progress = { ...run.progress }
  const patch = (stage: number, change: Partial<StageProgress>) => {
    if (progress[stage]) progress[stage] = { ...progress[stage], ...change }
  }
  switch (event.type) {
    case 'start':
      return { ...run, provider: event.provider, model: event.model, searchChain: event.search_chain }
    case 'stage':
      if (event.state === 'skipped' && progress[event.stage]?.state === 'done') return run
      patch(event.stage, {
        state: event.state,
        seconds: event.seconds,
        ...(event.state === 'active' ? { startedAt: Date.now() } : {}),
      })
      return { ...run, progress }
    case 'status':
      patch(event.stage, { message: event.message.replace(/…$/, '') })
      return { ...run, progress }
    case 'note': {
      if (!progress[event.stage]) return run
      patch(event.stage, { notes: [...progress[event.stage].notes, event.message] })
      const next = switchedToModel(event.message)
      return { ...run, progress, model: next ?? run.model }
    }
    case 'agent_done':
      return {
        ...run,
        agents: [
          ...run.agents,
          {
            stage: event.stage,
            agent: event.agent,
            seconds: event.seconds,
            inputTokens: event.input_tokens,
            outputTokens: event.output_tokens,
            cost: event.cost,
          },
        ],
      }
    case 'error': {
      const active = Object.entries(progress).find(([, p]) => p.state === 'active')
      if (active) patch(Number(active[0]), { state: 'error' })
      return { ...run, progress, running: false, finishedAt: Date.now(), error: event.message }
    }
    case 'result':
      return { ...run, running: false, finishedAt: Date.now() }
    default:
      return run
  }
}

export function firstUnfinishedStage(progress: Progress): number | undefined {
  return STAGES.find((s) => progress[s.id].state !== 'done' && progress[s.id].state !== 'skipped')?.id
}

export function formatDuration(ms: number): string {
  const total = Math.max(0, Math.round(ms / 1000))
  if (total < 60) return `${total}s`
  const m = Math.floor(total / 60)
  const s = total % 60
  return `${m}m ${s.toString().padStart(2, '0')}s`
}
