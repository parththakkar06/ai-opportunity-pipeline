import { Suspense, lazy, useCallback, useEffect, useRef, useState } from 'react'

import { fetchHealth, fetchRun, fetchRuns, streamAnalyze } from '@/api'
import { Intake } from '@/components/intake/Intake'
import { applyEvent, initialProgress, type RunState } from '@/components/run/progress'
import { Nav, RunDetails } from '@/components/shell/Nav'
import { useToast } from '@/components/shell/Toast'
import { useUrlState } from '@/lib/useUrlState'
import type { Health, ReportPayload, SavedRun, StreamEvent } from '@/types'

import { DataToggle } from './dev/DataToggle'
import { applyDataMode, readDataMode } from './dev/worstCase'

// Dev-only worst-case data (break-ui review): ?data=worst|empty|one swaps the report at the API boundary.
const DATA_MODE = import.meta.env.DEV ? readDataMode() : 'demo'

// Everything past the first screen loads on demand.
const Report = lazy(() => import('@/components/report/Report').then((m) => ({ default: m.Report })))
const RunTimeline = lazy(() => import('@/components/run/RunTimeline').then((m) => ({ default: m.RunTimeline })))
const HowItWorks = lazy(() => import('@/components/HowItWorks').then((m) => ({ default: m.HowItWorks })))
const ExportMenu = lazy(() => import('@/components/report/ExportMenu').then((m) => ({ default: m.ExportMenu })))
const EmailSheet = lazy(() => import('@/components/report/ExportMenu').then((m) => ({ default: m.EmailSheet })))

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [backendDown, setBackendDown] = useState(false)
  const [runs, setRuns] = useState<SavedRun[]>([])
  const [runsLoading, setRunsLoading] = useState(true)
  const [payload, setPayload] = useState<ReportPayload | null>(null)
  const [loadingReport, setLoadingReport] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [run, setRun] = useState<RunState | null>(null)
  const [emailOpen, setEmailOpen] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const url = useUrlState()
  const { notify } = useToast()

  const refreshRuns = useCallback(async () => {
    setRunsLoading(true)
    try {
      setRuns(await fetchRuns())
      setBackendDown(false)
    } catch {
      setBackendDown(true)
    } finally {
      setRunsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch(() => setBackendDown(true))
    void refreshRuns()
  }, [refreshRuns])

  // ?run=… decides which report is open: picking a saved report, finishing a run, Back/Forward, shared links.
  const loadedSlug = payload?.report.slug ?? null
  useEffect(() => {
    if (!url.run || url.run === loadedSlug) return
    let cancelled = false
    setLoadingReport(true)
    setLoadError(null)
    fetchRun(url.run)
      .then((data) => !cancelled && setPayload(applyDataMode(data, DATA_MODE)))
      .catch((e) => {
        if (cancelled) return
        const message = e instanceof Error ? e.message : String(e)
        setLoadError(message)
        notify({ tone: 'error', title: "Couldn't open that report", description: message })
      })
      .finally(() => !cancelled && setLoadingReport(false))
    return () => {
      cancelled = true
    }
  }, [url.run, loadedSlug, notify])

  const handleEvent = (event: StreamEvent) => {
    if (event.type === 'result') {
      const { type: _type, ...result } = event
      void _type
      setPayload(result)
      setRun((r) => (r ? { ...applyEvent(r, event), dismissed: true } : r))
      url.openRun(result.report.slug)
      notify({ tone: 'success', title: `Report ready: ${result.report.business_name}` })
      void refreshRuns()
      return
    }
    if (event.type === 'error') notify({ tone: 'error', title: 'Analysis stopped', description: event.message })
    setRun((r) => (r ? applyEvent(r, event) : r))
  }

  const analyze = async (company: string, website: string, includePrototype: boolean, fromStage = 1, runSlug?: string) => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    setRun((prev) => {
      const progress = initialProgress()
      const sameRun = !!prev && prev.company === company
      if (fromStage > 1 && sameRun) {
        for (const [id, p] of Object.entries(prev.progress)) if (Number(id) < fromStage) progress[Number(id)] = p
      }
      return {
        company,
        url: website,
        includePrototype,
        runSlug,
        fromStage,
        running: true,
        progress,
        startedAt: Date.now(),
        agents: fromStage > 1 && sameRun ? prev.agents.filter((a) => a.stage < fromStage) : [],
        model: sameRun ? prev.model : undefined,
      }
    })
    window.scrollTo({ top: 0 })
    setLoadError(null)
    try {
      await streamAnalyze(
        { company_name: company, url: website || undefined, include_prototype: includePrototype, from_stage: fromStage, run_slug: runSlug },
        handleEvent,
        controller.signal,
      )
      setRun((r) => (r && r.running ? { ...r, running: false, finishedAt: Date.now() } : r))
    } catch (e) {
      if (controller.signal.aborted) {
        setRun((r) => (r ? applyEvent(r, { type: 'error', message: 'Stopped by you.' }) : r))
      } else {
        const message = e instanceof Error ? e.message : String(e)
        setRun((r) => (r ? applyEvent(r, { type: 'error', message }) : r))
        notify({ tone: 'error', title: "Couldn't start the analysis", description: message })
      }
    }
  }

  const resumeSaved = (saved: SavedRun) => void analyze(saved.input_name, saved.website ?? '', false, saved.next_stage ?? 1, saved.slug)
  const running = !!run?.running
  const showRun = !!run && !run.dismissed && (run.running || !!run.error) && url.view !== 'how-it-works'
  const reportOpen = url.view === 'report' && !!payload && payload.report.slug === url.run && !showRun

  const notice = (
    <>
      {backendDown && (
        <p role="alert" className="border-l-2 border-negative py-1 pl-3 text-sm text-ink">
          Can't reach the API. Start it with <code className="font-mono text-[13px]">uvicorn api.index:app --port 8000</code>.
        </p>
      )}
      {health?.status === 'config_error' && (
        <p role="alert" className="border-l-2 border-caution py-1 pl-3 text-sm text-ink">
          {health.message}
        </p>
      )}
      {health?.status === 'ok' && health.llm_key_configured === false && (
        <p className="border-l-2 border-caution py-1 pl-3 text-sm text-ink">
          No API key for {health.provider} is set, so new research will fail. Saved reports still open.
        </p>
      )}
    </>
  )

  return (
    <div className="min-h-screen">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <Nav
        showCommandBar={url.view !== 'home' || showRun}
        runs={runs}
        running={running}
        onHome={url.goHome}
        onOpenRun={url.openRun}
        onAnalyze={(c) => void analyze(c, '', false)}
        onHowItWorks={url.openHowItWorks}
        actions={
          reportOpen && payload ? (
            <>
              <RunDetails meta={payload.run_meta} health={health} />
              <Suspense fallback={null}>
                <ExportMenu payload={payload} onEmail={() => setEmailOpen(true)} compactLabel />
              </Suspense>
            </>
          ) : null
        }
      />

      <div id="main" tabIndex={-1} className="focus:outline-none">
        {loadError && url.view === 'report' && (
          <p role="alert" className="mx-auto mt-6 max-w-[44rem] border-l-2 border-negative py-1 pl-3 text-sm text-ink [overflow-wrap:anywhere]">
            {loadError}
          </p>
        )}
        <Suspense fallback={<Loading />}>
          {showRun && run ? (
            <RunTimeline
              run={run}
              onStop={() => abortRef.current?.abort()}
              onResume={(from) => void analyze(run.company, run.url, run.includePrototype, from, run.runSlug)}
              onDismiss={() => setRun((r) => (r ? { ...r, dismissed: true } : r))}
            />
          ) : url.view === 'how-it-works' ? (
            <HowItWorks run={running ? run : null} meta={payload?.run_meta} />
          ) : url.view === 'report' ? (
            loadingReport || !reportOpen ? (
              loadError ? null : <Loading />
            ) : (
              <Report key={payload!.report.slug + (payload!.report.generated_at ?? '')} payload={payload!} onEmail={() => setEmailOpen(true)} />
            )
          ) : (
            <Intake
              runs={runs}
              runsLoading={runsLoading}
              running={running}
              notice={notice}
              onAnalyze={(c, u, p) => void analyze(c, u, p)}
              onOpenRun={url.openRun}
              onResume={resumeSaved}
              onHowItWorks={url.openHowItWorks}
            />
          )}
        </Suspense>
      </div>

      {import.meta.env.DEV && reportOpen && <DataToggle mode={DATA_MODE} />}
      {emailOpen && payload && (
        <Suspense fallback={null}>
          <EmailSheet slug={payload.report.slug} onClose={() => setEmailOpen(false)} />
        </Suspense>
      )}
    </div>
  )
}

function Loading() {
  return (
    <div className="mx-auto max-w-[44rem] px-4 pt-14" aria-busy="true" aria-live="polite">
      <span className="sr-only">Loading…</span>
      <div className="h-10 w-2/3 rounded-[3px] bg-tint" />
      <div className="mt-4 h-4 w-full rounded-[3px] bg-tint" />
      <div className="mt-2 h-4 w-5/6 rounded-[3px] bg-tint" />
    </div>
  )
}
