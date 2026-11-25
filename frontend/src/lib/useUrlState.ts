import { useCallback, useEffect, useState } from 'react'

// The URL is the source of truth: ?run=<slug> opens a report, ?view=how-it-works opens the pipeline map,
// and #section anchors point inside a report (the table of contents keeps them current). Old ?tab= links
// from the tabbed design are rewritten to the matching #section on load.

export type View = 'home' | 'report' | 'how-it-works' | 'orbital-demo'
export interface UrlState {
  run: string | null
  view: View
}

const SLUG = /^[a-z0-9][a-z0-9-]{0,120}$/
const LEGACY_TABS: Record<string, string> = {
  overview: 'overview',
  'key-info': 'key-information',
  challenges: 'challenges',
  opportunities: 'opportunities',
  pitch: 'ceo-pitch',
}

function read(): UrlState {
  const params = new URLSearchParams(window.location.search)
  const run = params.get('run')
  const valid = run && SLUG.test(run) ? run : null
  if (params.get('view') === 'how-it-works') return { run: null, view: 'how-it-works' }
  if (params.get('view') === 'orbital-demo') return { run: null, view: 'orbital-demo' }
  return { run: valid, view: valid ? 'report' : 'home' }
}

function migrateLegacyTab() {
  const params = new URLSearchParams(window.location.search)
  const tab = params.get('tab')
  if (!tab) return
  params.delete('tab')
  const hash = LEGACY_TABS[tab] ? `#${LEGACY_TABS[tab]}` : window.location.hash
  window.history.replaceState(null, '', `${window.location.pathname}${params.size ? `?${params}` : ''}${hash}`)
}

function urlFor(state: UrlState, keepHash: boolean): string {
  const params = new URLSearchParams()
  if (state.view === 'how-it-works' || state.view === 'orbital-demo') params.set('view', state.view)
  else if (state.run) params.set('run', state.run)
  const query = params.toString()
  return `${window.location.pathname}${query ? `?${query}` : ''}${keepHash ? window.location.hash : ''}`
}

export function useUrlState() {
  const [state, setState] = useState<UrlState>(() => {
    migrateLegacyTab()
    return read()
  })

  useEffect(() => {
    const onPop = () => setState(read())
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  const go = useCallback((next: UrlState) => {
    const url = urlFor(next, false)
    if (url !== `${window.location.pathname}${window.location.search}${window.location.hash}`) {
      window.history.pushState(null, '', url)
    }
    setState(next)
    window.scrollTo({ top: 0 })
  }, [])

  const openRun = useCallback((run: string) => go({ run, view: 'report' }), [go])
  const goHome = useCallback(() => go({ run: null, view: 'home' }), [go])
  const openHowItWorks = useCallback(() => go({ run: null, view: 'how-it-works' }), [go])
  return { ...state, openRun, goHome, openHowItWorks }
}
