import { LayoutGroup, m } from 'framer-motion'
import { useEffect, useId, useRef, type KeyboardEvent } from 'react'
import { indicatorSpring } from '../../lib/motion'
import type { ReportTab } from '../../lib/useUrlState'
import { cx } from '../ui'

export interface TabDef {
  id: ReportTab
  label: string
  short: string
  count?: number
}

export const tabId = (base: string, id: ReportTab) => `${base}-tab-${id}`
export const panelId = (base: string, id: ReportTab) => `${base}-panel-${id}`

/**
 * WAI-ARIA tabs: one tab stop for the whole list, then ←/→ move between tabs and Home/End jump to the ends.
 * Switching is "automatic" (arrows also activate). The active pill slides with a spring.
 */
export function SectionTabs({
  tabs,
  active,
  onChange,
  idBase,
}: {
  tabs: TabDef[]
  active: ReportTab
  onChange: (tab: ReportTab) => void
  idBase: string
}) {
  const layoutId = useId()
  const listRef = useRef<HTMLDivElement>(null)

  // Keep the active tab visible when the bar scrolls sideways on phones.
  useEffect(() => {
    listRef.current
      ?.querySelector<HTMLElement>(`[data-tab="${active}"]`)
      ?.scrollIntoView({ block: 'nearest', inline: 'nearest' })
  }, [active])

  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    const i = tabs.findIndex((t) => t.id === active)
    const next =
      e.key === 'ArrowRight' ? (i + 1) % tabs.length
      : e.key === 'ArrowLeft' ? (i - 1 + tabs.length) % tabs.length
      : e.key === 'Home' ? 0
      : e.key === 'End' ? tabs.length - 1
      : -1
    if (next < 0) return
    e.preventDefault()
    onChange(tabs[next].id)
    listRef.current?.querySelector<HTMLElement>(`[data-tab="${tabs[next].id}"]`)?.focus()
  }

  return (
    <LayoutGroup id={layoutId}>
      <div
        ref={listRef}
        role="tablist"
        aria-label="Report sections"
        className="-mx-1 flex snap-x gap-1 overflow-x-auto px-1 py-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {tabs.map((t, i) => {
          const selected = t.id === active
          return (
            <button
              key={t.id}
              type="button"
              role="tab"
              data-tab={t.id}
              id={tabId(idBase, t.id)}
              aria-selected={selected}
              aria-controls={selected ? panelId(idBase, t.id) : undefined}
              tabIndex={selected ? 0 : -1}
              onClick={() => onChange(t.id)}
              onKeyDown={onKeyDown}
              className={cx(
                'relative flex min-h-11 shrink-0 snap-start items-center gap-2 rounded-lg px-3.5 text-sm font-semibold transition-colors duration-150',
                selected ? 'text-on-primary' : 'text-muted-foreground hover:bg-muted hover:text-foreground',
              )}
            >
              {selected && (
                <m.span
                  layoutId="report-tab-pill"
                  className="absolute inset-0 rounded-lg bg-primary shadow-sm"
                  transition={indicatorSpring}
                  aria-hidden="true"
                />
              )}
              <span
                className={cx(
                  'relative flex h-5 w-5 items-center justify-center rounded-full text-xs font-bold tabular-nums',
                  selected ? 'bg-on-primary/20' : 'bg-muted text-secondary',
                )}
                aria-hidden="true"
              >
                {i + 1}
              </span>
              <span className="relative">
                <span className="hidden sm:inline">{t.label}</span>
                <span className="sm:hidden">{t.short}</span>
              </span>
              {t.count !== undefined && (
                <span className={cx('relative text-xs tabular-nums', selected ? 'opacity-80' : 'text-muted-foreground')}>
                  {t.count}
                  <span className="sr-only"> items</span>
                </span>
              )}
            </button>
          )
        })}
      </div>
    </LayoutGroup>
  )
}
