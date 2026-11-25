import { Download, FileText, Lightbulb, ListChecks, Scale, Search, ShieldCheck } from 'lucide-react'
import { useEffect, useRef } from 'react'

import RadialOrbitalTimeline, { type TimelineItem } from '@/components/ui/radial-orbital-timeline'
import type { RunMeta } from '@/types'

import type { RunState } from './run/progress'

type Step = Omit<TimelineItem, 'status' | 'energy'> & { stage: number }

const STEPS: Step[] = [
  {
    id: 1, stage: 1, title: 'Research', date: 'Stage 1 · LLM', category: 'llm', icon: Search, relatedIds: [2, 6],
    content: 'Searches the web (Tavily, then Serper, then DuckDuckGo with no key), reads up to 6 pages or PDFs, and a cheap model turns them into dated facts with ids. The newest source wins, and a leader is only named with evidence from the last 12 months.',
  },
  {
    id: 2, stage: 2, title: 'Challenges', date: 'Stage 2 · LLM', category: 'llm', icon: ListChecks, relatedIds: [1, 3],
    content: '5 to 8 operational, sales and customer-experience challenges, each argued from cited facts: evidence, reasoning, impact.',
  },
  {
    id: 3, stage: 3, title: 'Opportunities', date: 'Stage 3 · LLM', category: 'llm', icon: Lightbulb, relatedIds: [2, 4],
    content: '5 to 7 company-specific AI ideas, each with build vs buy from a curated vendor list, a 30/60/90-day pilot, data readiness and compliance notes from a curated list.',
  },
  {
    id: 4, stage: 3, title: 'Scoring', date: 'Stage 3 · Python', category: 'python', icon: Scale, relatedIds: [3, 5],
    content: 'The model scores five criteria; Python does the maths. ROI is discounted when its inputs are assumptions, and a conservative re-rank checks whether the winner holds.',
  },
  {
    id: 5, stage: 4, title: 'Pitch', date: 'Stage 4 · LLM', category: 'llm', icon: FileText, relatedIds: [4, 6],
    content: "A one-page pitch that opens on the CEO's own verified words (or the newest cited fact), with an ROI model computed in Python.",
  },
  {
    id: 6, stage: 4, title: 'Verifier', date: 'Stage 4 · Python', category: 'python', icon: ShieldCheck, relatedIds: [1, 5, 7],
    content: 'Every name, figure and period in the pitch is matched to a fact. Former leaders are replaced with their title, stale figures are flagged, and at most one cheap-model call settles the rest.',
  },
  {
    id: 7, stage: 5, title: 'Exports', date: 'No LLM', category: 'python', icon: Download, relatedIds: [6],
    content: 'One-page PDF, full report PDF with numbered sources, a 10-slide deck, an email draft (.eml with the PDF) and a zip, all built from the saved run.',
  },
]

/** The pipeline as an orbit: status from the current run, bar = this stage's share of the run's tokens. */
export function HowItWorks({ run, meta }: { run: RunState | null; meta?: RunMeta | null }) {
  const headingRef = useRef<HTMLHeadingElement>(null)
  useEffect(() => headingRef.current?.focus({ preventScroll: true }), [])

  const totals = meta?.stages ?? {}
  const all = Object.values(totals).reduce((n, s) => n + (s.input_tokens ?? 0) + (s.output_tokens ?? 0), 0)
  const items: TimelineItem[] = STEPS.map(({ stage, ...step }) => {
    const state = run && stage <= 4 ? run.progress[stage]?.state : undefined
    const status: TimelineItem['status'] = !run
      ? undefined
      : state === 'done' || state === 'skipped'
        ? 'completed'
        : state === 'active'
          ? 'in-progress'
          : stage === 5 && !run.running && !run.error
            ? 'completed'
            : 'pending'
    const s = totals[String(stage)]
    // Python-only steps use no tokens, so they get no bar; LLM steps show their share once a report is open.
    const share = step.category !== 'llm' ? -1 : all && s ? Math.round((((s.input_tokens ?? 0) + (s.output_tokens ?? 0)) / all) * 100) : -1
    return { ...step, status, energy: share }
  })

  return (
    <div className="mx-auto max-w-[60rem] px-4 pt-14 pb-24 sm:px-6">
      <h1 ref={headingRef} tabIndex={-1} className="display text-[2.25rem] text-ink sm:text-[2.75rem]">
        How it works
      </h1>
      <p className="prose-serif mt-3 text-ink-2">
        Four model stages, with Python doing the parts that must be exact: provenance, scoring, verification and
        exports. Select a step to see what it does and what it connects to.
        {meta ? ' Bars show each stage’s share of the open report’s tokens.' : ''}
      </p>
      <RadialOrbitalTimeline
        timelineData={items}
        label="Pipeline steps"
        energyLabel="Share of this run’s tokens"
        className="mt-10"
      />
    </div>
  )
}
