import { useCallback, useEffect, useState } from 'react'

export const REPORT_TABS = ['overview', 'key-info', 'challenges', 'opportunities', 'pitch'] as const
export type ReportTab = (typeof REPORT_TABS)[number]

export interface UrlState {
  run: string | null
  tab: ReportTab
}

const SLUG = /^[a-z0-9][a-z0-9-]{0,120}$/

function read(): UrlState {
  const params = new URLSearchParams(window.location.search)
  const run = params.get('run')
  const tab = params.get('tab') as ReportTab | null
  return {
    run: run && SLUG.test(run) ? run : null,
    tab: tab && REPORT_TABS.includes(tab) ? tab : 'overview',
  }
}

function write(state: UrlState, mode: 'push' | 'replace') {
  const params = new URLSearchParams(window.location.search)
  if (state.run) params.set('run', state.run)
  else params.delete('run')
  if (state.run && state.tab !== 'overview') params.set('tab', state.tab)
  else params.delete('tab')
  // Section-level filters (e.g. ?cat= on Challenges) belong to one tab of one report.
  if (!state.run || state.tab !== 'challenges') params.delete('cat')
  const query = params.toString()
  const url = `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`
  if (url === `${window.location.pathname}${window.location.search}${window.location.hash}`) return
  window.history[mode === 'push' ? 'pushState' : 'replaceState'](null, '', url)
}

/**
 * Keeps the open report and tab in the URL (?run=sobha&tab=challenges), so links can be shared and
 * Back/Forward work. Opening a different report adds a history entry. Switching tabs replaces the
 * current entry, so Back doesn't step through every tab click.
 */
export function useUrlState() {
  const [state, setState] = useState<UrlState>(read)

  useEffect(() => {
    const onPop = () => setState(read())
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  const openRun = useCallback((run: string | null, tab: ReportTab = 'overview') => {
    const next = { run, tab }
    const params = new URLSearchParams(window.location.search)
    if (params.get('run') !== run) {
      params.delete('cat')
      window.history.replaceState(window.history.state, '', `${window.location.pathname}?${params}`)
    }
    write(next, 'push')
    setState(next)
  }, [])

  const setTab = useCallback((tab: ReportTab) => {
    setState((prev) => {
      const next = { ...prev, tab }
      write(next, 'replace')
      return next
    })
  }, [])

  return { ...state, openRun, setTab }
}
