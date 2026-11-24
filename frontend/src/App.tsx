import { Suspense, lazy, useCallback, useEffect, useRef, useState } from 'react'
import { fetchHealth, fetchRun, fetchRuns, streamAnalyze } from './api'
import { CompanyPicker } from './components/intake/CompanyPicker'
import { SavedRuns } from './components/intake/SavedRuns'
import { applyEvent, initialProgress, type RunState } from './components/run/progress'
import { ReportSkeleton } from './components/ReportSkeleton'
import { MobileSheet } from './components/shell/MobileSheet'
import { useToast } from './components/shell/Toast'
import { ThemeToggle } from './components/ThemeToggle'
import { AlertIcon, Button, Card, PlusIcon, SparkIcon, Spinner } from './components/ui'
import { useIsDesktop } from './lib/useMediaQuery'
import { useUrlState } from './lib/useUrlState'
import type { Health, ReportPayload, SavedRun, StreamEvent } from './types'

// The report and live-run views aren't needed for the first screen, so they load on demand.
const ReportView = lazy(() => import('./components/ReportView').then((mod) => ({ default: mod.ReportView })))
const RunView = lazy(() => import('./components/run/RunView').then((mod) => ({ default: mod.RunView })))

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [backendDown, setBackendDown] = useState(false)
  const [runs, setRuns] = useState<SavedRun[]>([])
  const [runsLoading, setRunsLoading] = useState(true)
  const [payload, setPayload] = useState<ReportPayload | null>(null)
  const [loadingReport, setLoadingReport] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [run, setRun] = useState<RunState | null>(null)
  const [sheetOpen, setSheetOpen] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const url = useUrlState()
  const isDesktop = useIsDesktop()
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

  // The URL (?run=…) is the source of truth for which report is open: picking a saved report, finishing
  // an analysis, Back/Forward and shared links all go through it.
  const loadedSlug = payload?.report.slug ?? null
  useEffect(() => {
    if (!url.run) {
      setPayload(null)
      return
    }
    if (url.run === loadedSlug) return
    let cancelled = false
    setLoadingReport(true)
    setLoadError(null)
    fetchRun(url.run)
      .then((data) => !cancelled && setPayload(data))
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

  // When a report opens, close the mobile sheet. (ReportView moves focus to its own title once it has
  // loaded, since it's lazy-loaded and may not exist yet at this point.)
  const reportKey = payload ? payload.report.slug + (payload.report.generated_at ?? '') : null
  useEffect(() => {
    if (reportKey) setSheetOpen(false)
  }, [reportKey])

  // Close the sheet automatically if the window grows to desktop size.
  useEffect(() => {
    if (isDesktop) setSheetOpen(false)
  }, [isDesktop])

  const openRun = (slug: string) => url.openRun(slug)

  const handleEvent = (event: StreamEvent) => {
    if (event.type === 'result') {
      const { type: _type, ...result } = event
      void _type
      setPayload(result)
      url.openRun(result.report.slug)
      setRun((r) => (r ? applyEvent(r, event) : r))
      notify({ tone: 'success', title: `Report ready: ${result.report.business_name}` })
      void refreshRuns()
      return
    }
    if (event.type === 'error') notify({ tone: 'error', title: 'Analysis stopped', description: event.message })
    setRun((r) => (r ? applyEvent(r, event) : r))
  }

  const analyze = async (
    company: string,
    website: string,
    includePrototype: boolean,
    fromStage = 1,
    runSlug?: string,
  ) => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    setSheetOpen(false)
    setRun((prev) => {
      const progress = initialProgress()
      const sameRun = !!prev && prev.company === company
      // When resuming the same run, keep its finished stages, notes and agent results visible.
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
    setLoadError(null)
    try {
      await streamAnalyze(
        {
          company_name: company,
          url: website || undefined,
          include_prototype: includePrototype,
          from_stage: fromStage,
          run_slug: runSlug,
        },
        handleEvent,
        controller.signal,
      )
      setRun((r) => (r && r.running ? { ...r, running: false, finishedAt: Date.now() } : r))
    } catch (e) {
      if (controller.signal.aborted) {
        setRun((r) =>
          r ? applyEvent(r, { type: 'error', message: 'Stopped by you. Completed stages are saved on the server.' }) : r,
        )
      } else {
        const message = e instanceof Error ? e.message : String(e)
        setRun((r) => (r ? applyEvent(r, { type: 'error', message }) : r))
        notify({ tone: 'error', title: "Couldn't start the analysis", description: message })
      }
    }
  }

  const resumeSaved = (saved: SavedRun) =>
    void analyze(saved.input_name, saved.website ?? '', false, saved.next_stage ?? 1, saved.slug)

  const cancel = () => abortRef.current?.abort()
  const running = !!run?.running

  const intake = (
    <>
      <CompanyPicker running={running} onAnalyze={(c, u, p) => void analyze(c, u, p)} onCancel={cancel} />
      <SavedRuns
        runs={runs}
        loading={runsLoading}
        selectedSlug={payload?.report.slug ?? null}
        running={running}
        onOpen={openRun}
        onResume={resumeSaved}
      />
    </>
  )
  const showRun = !!run && (run.running || (!!run.error && !run.dismissed))

  const notices = (
    <>
      {backendDown && (
        <div className="flex gap-2 rounded-xl bg-danger-soft p-3 text-sm text-danger-foreground ring-1 ring-danger/30" role="alert">
          <AlertIcon className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            Can't reach the API. Start it with <code className="font-mono">uvicorn api.index:app --port 8000</code>.
          </span>
        </div>
      )}
      {health?.status === 'config_error' && (
        <div className="rounded-xl bg-warning-soft p-3 text-sm text-warning-foreground ring-1 ring-warning/30" role="alert">
          {health.message}
        </div>
      )}
    </>
  )

  return (
    <div className="min-h-screen">
      <a href="#workspace" className="skip-link">
        Skip to report
      </a>
      <header className="no-print sticky top-0 z-30 border-b border-border bg-card/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-[1440px] items-center justify-between gap-3 px-4 sm:px-6">
          <a href="/" className="flex min-w-0 items-center gap-2.5 rounded-lg">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary text-on-primary">
              <SparkIcon />
            </span>
            <span className="min-w-0">
              <span className="block truncate text-sm font-bold leading-tight text-foreground">AI Opportunity Studio</span>
              <span className="hidden truncate text-xs leading-tight text-muted-foreground sm:block">
                Research → Challenges → AI opportunities → CEO pitch
              </span>
            </span>
          </a>
          <div className="flex items-center gap-1.5">
            {health?.status === 'ok' && (
              <p className="hidden items-center gap-2 rounded-full border border-border bg-subtle px-3 py-1 text-xs text-muted-foreground xl:flex">
                <span
                  className={`h-2 w-2 rounded-full ${health.llm_key_configured ? 'bg-success' : 'bg-danger'}`}
                  aria-hidden="true"
                />
                <span>
                  {health.provider} · <span className="font-medium text-secondary">{health.model}</span> · search:{' '}
                  {health.search_provider}
                </span>
                {!health.llm_key_configured && <span className="font-semibold text-danger-foreground">API key missing</span>}
              </p>
            )}
            {!isDesktop && (
              <Button variant="primary" onClick={() => setSheetOpen(true)} className="px-3">
                <PlusIcon />
                <span className="hidden sm:inline">New analysis</span>
                <span className="sm:hidden">New</span>
              </Button>
            )}
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="print-reset mx-auto grid max-w-[1440px] gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[360px_minmax(0,1fr)] lg:gap-8">
        {isDesktop && (
          <aside
            aria-label="New analysis and saved reports"
            className="no-print sticky top-[5.5rem] max-h-[calc(100vh-7rem)] space-y-4 self-start overflow-y-auto overscroll-contain pb-2 [scrollbar-gutter:stable]"
          >
            {notices}
            {intake}
          </aside>
        )}

        <section id="workspace" tabIndex={-1} aria-label="Report" className="min-w-0 scroll-mt-24 focus:outline-none">
          {!isDesktop && <div className="no-print mb-5 space-y-4 empty:hidden">{notices}</div>}
          {loadError && (
            <div className="mb-4 rounded-xl bg-danger-soft p-3 text-sm text-danger-foreground ring-1 ring-danger/30 [overflow-wrap:anywhere]" role="alert">
              {loadError}
            </div>
          )}
          <Suspense fallback={<ReportSkeleton />}>
          {showRun && run ? (
            <RunView
              run={run}
              onStop={cancel}
              onResume={(fromStage) => void analyze(run.company, run.url, run.includePrototype, fromStage, run.runSlug)}
              onDismiss={() => setRun((r) => (r ? { ...r, dismissed: true } : r))}
            />
          ) : loadingReport ? (
            <ReportSkeleton />
          ) : payload ? (
            <ReportView key={reportKey ?? undefined} payload={payload} tab={url.tab} onTabChange={url.setTab} />
          ) : (
            <EmptyState running={running} onStart={isDesktop ? undefined : () => setSheetOpen(true)} savedCount={runs.length} />
          )}
          </Suspense>
        </section>
      </main>

      {!isDesktop && (
        <MobileSheet open={sheetOpen} onClose={() => setSheetOpen(false)} title="New analysis">
          {intake}
        </MobileSheet>
      )}
    </div>
  )
}

function EmptyState({ running, onStart, savedCount }: { running: boolean; onStart?: () => void; savedCount: number }) {
  const sections = [
    ['Company Overview', 'What they do, scale, geographic presence'],
    ['Key Business Information', 'Projects, developments, expansion, RERA & financials'],
    ['Potential Business Challenges', 'Operational, sales, CX — each with explicit reasoning'],
    ['AI Opportunities', 'Mapped to real projects, buyer journey and site/sales ops'],
    ['Personalized CEO Pitch', 'One page: why we reached out, opportunities, solutions'],
  ]
  return (
    <Card className="p-6 sm:p-12">
      <div className="mx-auto max-w-xl text-center">
        <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-accent-soft text-accent">
          {running ? <Spinner className="h-6 w-6" /> : <SparkIcon className="h-6 w-6" />}
        </span>
        <h1 className="mt-4 text-2xl font-bold text-foreground">{running ? 'Agents at work…' : 'Pick a company to assess'}</h1>
        <p className="mt-2 text-base text-muted-foreground">
          {running
            ? 'Follow the stages as they run. The report opens here when the CEO pitch is ready.'
            : 'Choose an example company or type your own, or open a saved report to view it without using any quota.'}
        </p>
        {onStart && !running && (
          <Button variant="primary" onClick={onStart} className="mt-5">
            <PlusIcon />
            {savedCount > 0 ? 'New analysis or saved report' : 'Start a new analysis'}
          </Button>
        )}
      </div>
      <ol className="mx-auto mt-8 grid max-w-2xl gap-3 sm:grid-cols-2" aria-label="What the report contains">
        {sections.map(([title, blurb], i) => (
          <li key={title} className="flex gap-3 rounded-xl bg-subtle p-3.5">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-card text-sm font-bold text-secondary ring-1 ring-border">
              {i + 1}
            </span>
            <div>
              <p className="text-sm font-semibold text-foreground">{title}</p>
              <p className="text-sm text-muted-foreground">{blurb}</p>
            </div>
          </li>
        ))}
      </ol>
    </Card>
  )
}
