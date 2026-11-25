import * as React from 'react'

import { cn } from '@/lib/utils'

/**
 * A small, accessible menu (WAI-ARIA menu button pattern): Enter/Space/ArrowDown opens it, arrow keys,
 * Home and End move, Esc or Tab closes it and focus returns to the trigger. No animation on keyboard
 * use beyond a 160ms fade (it's a floating layer, opened occasionally).
 */
export function Menu({
  label,
  trigger,
  align = 'end',
  children,
}: {
  label: string
  trigger: (props: React.ButtonHTMLAttributes<HTMLButtonElement> & { ref: React.Ref<HTMLButtonElement> }) => React.ReactNode
  align?: 'start' | 'end'
  children: (close: () => void) => React.ReactNode
}) {
  const [open, setOpen] = React.useState(false)
  const id = React.useId()
  const triggerRef = React.useRef<HTMLButtonElement>(null)
  const listRef = React.useRef<HTMLDivElement>(null)
  const items = () => Array.from(listRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? [])

  const close = React.useCallback((refocus = true) => {
    setOpen(false)
    if (refocus) triggerRef.current?.focus()
  }, [])

  React.useEffect(() => {
    if (!open) return
    items()[0]?.focus()
    const onDown = (e: MouseEvent) => {
      if (!listRef.current?.contains(e.target as Node) && !triggerRef.current?.contains(e.target as Node)) close(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [open, close])

  const onKey = (e: React.KeyboardEvent) => {
    const list = items()
    const i = list.indexOf(document.activeElement as HTMLElement)
    const go = (n: number) => {
      e.preventDefault()
      list[(n + list.length) % list.length]?.focus()
    }
    if (e.key === 'ArrowDown') go(i + 1)
    else if (e.key === 'ArrowUp') go(i - 1)
    else if (e.key === 'Home') go(0)
    else if (e.key === 'End') go(list.length - 1)
    else if (e.key === 'Escape') {
      e.preventDefault()
      close()
    } else if (e.key === 'Tab') close(false)
  }

  return (
    <div className="relative">
      {trigger({
        ref: triggerRef,
        'aria-haspopup': 'menu',
        'aria-expanded': open,
        'aria-controls': open ? id : undefined,
        onClick: () => setOpen((v) => !v),
        onKeyDown: (e) => {
          if (e.key === 'ArrowDown' && !open) {
            e.preventDefault()
            setOpen(true)
          }
        },
      })}
      {open && (
        <div
          ref={listRef}
          id={id}
          role="menu"
          aria-label={label}
          onKeyDown={onKey}
          style={{ ['--origin' as string]: align === 'end' ? 'top right' : 'top left' }}
          className={cn(
            'float-in absolute z-30 mt-1.5 min-w-60 rounded-md border border-rule bg-sheet p-1 shadow-float',
            align === 'end' ? 'right-0' : 'left-0',
          )}
        >
          {children(() => close())}
        </div>
      )}
    </div>
  )
}

export function MenuItem({
  children,
  hint,
  href,
  download,
  external,
  onSelect,
}: {
  children: React.ReactNode
  hint?: string
  href?: string
  download?: boolean
  external?: boolean
  onSelect?: () => void
}) {
  const cls =
    'flex w-full flex-col rounded-[3px] px-2.5 py-1.5 text-left outline-none hover:bg-tint focus-visible:bg-tint focus-visible:outline-none [@media(pointer:coarse)]:min-h-11 justify-center'
  const body = (
    <>
      <span className="text-sm text-ink">{children}</span>
      {hint && <span className="meta">{hint}</span>}
    </>
  )
  if (href)
    return (
      <a
        role="menuitem"
        tabIndex={-1}
        href={href}
        download={download || undefined}
        target={external ? '_blank' : undefined}
        rel={external ? 'noreferrer noopener' : undefined}
        onClick={onSelect}
        className={cls}
      >
        {body}
        {external && <span className="sr-only"> (opens in a new tab)</span>}
      </a>
    )
  return (
    <button role="menuitem" tabIndex={-1} type="button" onClick={onSelect} className={cls}>
      {body}
    </button>
  )
}

export function MenuSeparator() {
  return <div role="separator" className="my-1 h-px bg-rule" />
}
