import { ArrowRight, Link as LinkIcon } from 'lucide-react'
import { useEffect, useRef, useState, type ElementType, type KeyboardEvent } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

// Radial orbital timeline (from the shadcn-style component the user supplied), adapted to the paper
// design in docs/DESIGN_DIRECTION.md: no gradients, glows, pings or perpetual rotation. The ring only
// turns to bring a chosen node to the top (400ms ease-out, none with reduced motion). Every node is a
// button: Tab/arrow keys move between nodes, Enter/Space opens one, Esc closes it. Below 520px wide the
// orbit becomes a plain ordered list, which reads better on a phone.

export interface TimelineItem {
  id: number
  title: string
  date: string
  content: string
  category: string
  icon: ElementType
  relatedIds: number[]
  /** Optional: omit it when there's no live state to show. */
  status?: 'completed' | 'in-progress' | 'pending'
  /** 0-100, drawn as a thin bar in the detail card (labelled by `energyLabel`); negative hides the bar. */
  energy: number
}

interface RadialOrbitalTimelineProps {
  timelineData: TimelineItem[]
  /** Label for the 0-100 bar in the detail card. */
  energyLabel?: string
  /** Accessible name for the whole diagram. */
  label?: string
  className?: string
}

const STATUS: Record<NonNullable<TimelineItem['status']>, { text: string; variant: 'positive' | 'brand' | 'default' }> = {
  completed: { text: 'Complete', variant: 'positive' },
  'in-progress': { text: 'In progress', variant: 'brand' },
  pending: { text: 'Pending', variant: 'default' },
}

export default function RadialOrbitalTimeline({
  timelineData,
  energyLabel = 'Share',
  label = 'Timeline',
  className,
}: RadialOrbitalTimelineProps) {
  const [activeId, setActiveId] = useState<number | null>(null)
  const [rotation, setRotation] = useState(-90) // first node at the top
  const [size, setSize] = useState(640)
  const containerRef = useRef<HTMLDivElement>(null)
  const nodeRefs = useRef<Record<number, HTMLButtonElement | null>>({})

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => setSize(entry.contentRect.width))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const compact = size < 520
  const radius = Math.max(120, Math.min(210, size / 2 - 90))
  const active = timelineData.find((i) => i.id === activeId) ?? null
  const related = new Set(active?.relatedIds ?? [])

  const open = (id: number) => {
    if (activeId === id) {
      setActiveId(null)
      return
    }
    const index = timelineData.findIndex((i) => i.id === id)
    // Rotate the ring the short way round so the chosen node sits at the top (-90°).
    const target = -90 - (index / timelineData.length) * 360
    setRotation((prev) => prev + ((((target - prev) % 360) + 540) % 360) - 180)
    setActiveId(id)
  }

  const onNodeKey = (e: KeyboardEvent, index: number) => {
    const n = timelineData.length
    const go = (i: number) => {
      e.preventDefault()
      nodeRefs.current[timelineData[(i + n) % n].id]?.focus()
    }
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') go(index + 1)
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') go(index - 1)
    else if (e.key === 'Escape') setActiveId(null)
  }

  const detail = active && (
    <Card className="w-72 max-w-full text-left">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-2">
          {active.status ? <Badge variant={STATUS[active.status].variant}>{STATUS[active.status].text}</Badge> : <span />}
          <span className="meta num">{active.date}</span>
        </div>
        <CardTitle className="mt-1 text-base">{active.title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm text-ink-2">
        <p>{active.content}</p>
        {active.energy >= 0 && (
        <div>
          <div className="meta mb-1 flex justify-between">
            <span>{energyLabel}</span>
            <span className="num">{active.energy}%</span>
          </div>
          <div className="h-1 overflow-hidden rounded-full bg-tint" aria-hidden="true">
            <div className="h-full bg-brand" style={{ width: `${active.energy}%` }} />
          </div>
        </div>
        )}
        {active.relatedIds.length > 0 && (
          <div className="border-t border-rule pt-3">
            <p className="meta mb-2 flex items-center gap-1">
              <LinkIcon className="size-3" strokeWidth={1.5} aria-hidden="true" />
              Connected
            </p>
            <div className="flex flex-wrap gap-1.5">
              {active.relatedIds.map((rid) => {
                const item = timelineData.find((i) => i.id === rid)
                return item ? (
                  <Button key={rid} variant="outline" size="sm" onClick={() => open(rid)}>
                    {item.title}
                    <ArrowRight strokeWidth={1.5} aria-hidden="true" />
                  </Button>
                ) : null
              })}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )

  if (compact) {
    return (
      <div ref={containerRef} className={cn('w-full', className)}>
        <ol aria-label={label} className="divide-y divide-rule border-y border-rule">
          {timelineData.map((item) => {
            const Icon = item.icon
            const isOpen = activeId === item.id
            return (
              <li key={item.id}>
                <button
                  type="button"
                  aria-expanded={isOpen}
                  onClick={() => open(item.id)}
                  className="flex w-full items-center gap-3 py-3 text-left [@media(pointer:coarse)]:min-h-11"
                >
                  <span className="flex size-8 shrink-0 items-center justify-center rounded-full border border-rule-strong text-ink-2">
                    <Icon className="size-4" strokeWidth={1.5} aria-hidden="true" />
                  </span>
                  <span className="flex-1 text-sm font-medium text-ink">{item.title}</span>
                  {item.status && <Badge variant={STATUS[item.status].variant}>{STATUS[item.status].text}</Badge>}
                </button>
                {isOpen && <div className="pb-4">{detail}</div>}
              </li>
            )
          })}
        </ol>
      </div>
    )
  }

  const box = radius * 2 + 140
  return (
    <div ref={containerRef} className={cn('w-full', className)}>
      <div
        role="group"
        aria-label={label}
        className="relative mx-auto"
        style={{ width: box, height: box }}
        onClick={(e) => e.target === e.currentTarget && setActiveId(null)}
      >
        {/* orbit and centre */}
        <div
          aria-hidden="true"
          className="absolute rounded-full border border-rule"
          style={{ inset: 70, width: radius * 2, height: radius * 2 }}
        />
        <div
          aria-hidden="true"
          className="absolute size-3 rounded-full bg-ink"
          style={{ left: box / 2 - 6, top: box / 2 - 6 }}
        />

        {timelineData.map((item, index) => {
          const angle = (index / timelineData.length) * 360 + rotation
          const rad = (angle * Math.PI) / 180
          const x = box / 2 + radius * Math.cos(rad)
          const y = box / 2 + radius * Math.sin(rad)
          const Icon = item.icon
          const isOpen = activeId === item.id
          const isRelated = related.has(item.id)
          return (
            <div
              key={item.id}
              className="absolute transition-transform duration-[400ms] ease-[var(--ease-out)] motion-reduce:transition-none"
              style={{ transform: `translate(${x - 20}px, ${y - 20}px)`, zIndex: isOpen ? 20 : 10, left: 0, top: 0 }}
            >
              <button
                ref={(el) => {
                  nodeRefs.current[item.id] = el
                }}
                type="button"
                aria-expanded={isOpen}
                aria-label={item.status ? `${item.title}, ${STATUS[item.status].text}` : item.title}
                onClick={() => open(item.id)}
                onKeyDown={(e) => onNodeKey(e, index)}
                className={cn(
                  'pressable flex size-10 items-center justify-center rounded-full border bg-sheet',
                  isOpen
                    ? 'border-ink bg-ink text-paper'
                    : isRelated
                      ? 'border-brand text-brand'
                      : item.status === 'pending'
                        ? 'border-rule-strong text-ink-3'
                        : 'border-ink-2 text-ink',
                )}
              >
                <Icon className="size-4" strokeWidth={1.5} aria-hidden="true" />
              </button>
              <span
                className={cn(
                  'pointer-events-none absolute top-12 left-1/2 -translate-x-1/2 whitespace-nowrap text-[13px]',
                  isOpen ? 'font-semibold text-ink' : 'text-ink-2',
                )}
              >
                {item.title}
              </span>
              {isOpen && <div className="float-in absolute top-20 left-1/2 -translate-x-1/2 [--origin:top_center]">{detail}</div>}
            </div>
          )
        })}
      </div>
    </div>
  )
}
