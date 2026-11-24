import { AnimatePresence, m } from 'framer-motion'
import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { fadeRise } from '../lib/motion'
import type { ReportTab } from '../lib/useUrlState'
import type { ReportPayload } from '../types'
import { ChallengesSection } from './report/ChallengesSection'
import { CeoPitchSection } from './report/CeoPitchSection'
import { KeyInfoSection } from './report/KeyInfoSection'
import { OpportunitiesSection } from './report/OpportunitiesSection'
import { OverviewSection } from './report/OverviewSection'
import { ReportActions, ReportHeader, useReportActions } from './report/ReportHeader'
import { SectionTabs, panelId, tabId, type TabDef } from './report/SectionTabs'

export function ReportView({
  payload,
  tab,
  onTabChange,
}: {
  payload: ReportPayload
  tab: ReportTab
  onTabChange: (tab: ReportTab) => void
}) {
  const { report } = payload
  const idBase = useId().replace(/:/g, '')
  const actions = useReportActions(payload)
  const [entrance, setEntrance] = useState(true) // the staggered entrance plays once per report
  const [highlight, setHighlight] = useState<string | null>(null)
  const headerRef = useRef<HTMLDivElement>(null)
  const [compact, setCompact] = useState(false)

  // A newly opened report takes keyboard focus (ReportView remounts per report via its key), so screen
  // reader and keyboard users land on the title instead of staying in the sidebar.
  useEffect(() => {
    const frame = requestAnimationFrame(() => document.getElementById('report-title')?.focus())
    return () => cancelAnimationFrame(frame)
  }, [])
  const [printKit, setPrintKit] = useState(false)

  // Show the compact title + actions in the sticky bar once the full header has scrolled away.
  useEffect(() => {
    const el = headerRef.current
    if (!el) return
    const observer = new IntersectionObserver(([entry]) => setCompact(!entry.isIntersecting), {
      rootMargin: '-72px 0px 0px 0px',
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  const changeTab = useCallback(
    (next: ReportTab) => {
      setEntrance(false)
      if (next !== 'challenges') setHighlight(null)
      onTabChange(next)
    },
    [onTabChange],
  )

  const jumpToChallenge = useCallback(
    (id: string) => {
      setEntrance(false)
      setHighlight(id)
      onTabChange('challenges')
      window.setTimeout(() => setHighlight((h) => (h === id ? null : h)), 2600)
    },
    [onTabChange],
  )

  // Print / Save as PDF: show the pitch tab, name the PDF after the company, then open the print dialog.
  const printPitch = useCallback(() => {
    const open = () => {
      const previous = document.title
      document.title = `${report.business_name} – CEO pitch`
      const restore = () => {
        document.title = previous
        window.removeEventListener('afterprint', restore)
      }
      window.addEventListener('afterprint', restore)
      window.print()
    }
    if (tab === 'pitch') open()
    else {
      changeTab('pitch')
      window.setTimeout(open, 500) // after the tab switch finishes rendering
    }
  }, [tab, changeTab, report.business_name])

  const tabs: TabDef[] = [
    { id: 'overview', label: 'Company Overview', short: 'Overview' },
    { id: 'key-info', label: 'Key Business Info', short: 'Key info' },
    { id: 'challenges', label: 'Challenges', short: 'Challenges', count: report.business_challenges.length },
    { id: 'opportunities', label: 'AI Opportunities', short: 'AI ideas', count: report.ai_opportunities.length || undefined },
    { id: 'pitch', label: 'CEO Pitch', short: 'Pitch' },
  ]

  return (
    <div className="space-y-4" data-print-mode={tab} data-print-kit={printKit}>
      <div ref={headerRef} className="print-hide-on-pitch">
        <ReportHeader payload={payload} actions={actions} onPrint={report.ceo_pitch ? printPitch : undefined} />
      </div>

      <div className="no-print sticky top-16 z-20 -mx-4 border-b border-border bg-background/95 px-4 py-2 backdrop-blur sm:-mx-6 sm:px-6 lg:mx-0 lg:rounded-xl lg:border lg:px-3">
        <AnimatePresence initial={false}>
          {compact && (
            <m.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.18 }}
              className="overflow-hidden"
            >
              <div className="flex items-center justify-between gap-3 pt-1 pb-2">
                <p className="min-w-0 truncate text-base font-bold text-foreground" translate="no">
                  {report.business_name}
                </p>
                <ReportActions actions={actions} prototypeUrl={null} compact />
              </div>
            </m.div>
          )}
        </AnimatePresence>
        <SectionTabs tabs={tabs} active={tab} onChange={changeTab} idBase={idBase} />
      </div>

      <AnimatePresence mode="wait" initial={false}>
        <m.div
          key={tab}
          role="tabpanel"
          id={panelId(idBase, tab)}
          aria-labelledby={tabId(idBase, tab)}
          tabIndex={0}
          variants={fadeRise}
          initial="initial"
          animate="animate"
          exit="exit"
          className="rounded-2xl focus-visible:outline-offset-4"
        >
          {tab === 'overview' && <OverviewSection report={report} entrance={entrance} />}
          {tab === 'key-info' && <KeyInfoSection report={report} entrance={entrance} />}
          {tab === 'challenges' && <ChallengesSection report={report} entrance={entrance} highlightId={highlight} />}
          {tab === 'opportunities' && (
            <OpportunitiesSection report={report} entrance={entrance} onJumpToChallenge={jumpToChallenge} />
          )}
          {tab === 'pitch' && (
            <CeoPitchSection
              report={report}
              entrance={entrance}
              onPrint={printPitch}
              onCopy={actions.copyPitch}
              copied={actions.copied}
              includeKit={printKit}
              onIncludeKitChange={setPrintKit}
            />
          )}
        </m.div>
      </AnimatePresence>
    </div>
  )
}
