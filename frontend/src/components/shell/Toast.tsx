import { AnimatePresence, m } from 'framer-motion'
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react'
import { duration, ease } from '../../lib/motion'
import { AlertIcon, CheckIcon, CloseIcon, InfoIcon, cx } from '../ui'

type Tone = 'success' | 'error' | 'info'
interface Toast {
  id: number
  tone: Tone
  title: string
  description?: string
}
interface ToastApi {
  notify: (toast: Omit<Toast, 'id'>) => void
}

const ToastContext = createContext<ToastApi>({ notify: () => {} })
export const useToast = () => useContext(ToastContext)

const TONE: Record<Tone, { icon: ReactNode; className: string }> = {
  success: { icon: <CheckIcon className="h-4 w-4" />, className: 'text-success' },
  error: { icon: <AlertIcon className="h-4 w-4" />, className: 'text-danger' },
  info: { icon: <InfoIcon className="h-4 w-4" />, className: 'text-accent' },
}
const LIFETIME_MS = { success: 3500, info: 4500, error: 8000 }
const MAX_VISIBLE = 3

/** Short confirmations ("Pitch copied", "Report ready"). Announced politely to screen readers. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(1)

  const dismiss = useCallback((id: number) => setToasts((all) => all.filter((t) => t.id !== id)), [])
  const notify = useCallback(
    (toast: Omit<Toast, 'id'>) => {
      const id = nextId.current++
      setToasts((all) => [...all.slice(-(MAX_VISIBLE - 1)), { ...toast, id }])
      window.setTimeout(() => dismiss(id), LIFETIME_MS[toast.tone])
    },
    [dismiss],
  )
  const api = useMemo(() => ({ notify }), [notify])

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        role="status"
        aria-live="polite"
        className="no-print pointer-events-none fixed inset-x-4 bottom-4 z-50 flex flex-col items-center gap-2 sm:inset-x-auto sm:right-6 sm:bottom-6 sm:items-end"
      >
        <AnimatePresence initial={false}>
          {toasts.map((t) => (
            <m.div
              key={t.id}
              layout
              initial={{ opacity: 0, y: 12, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1, transition: { duration: duration.base, ease: ease.out } }}
              exit={{ opacity: 0, y: 6, transition: { duration: 0.16, ease: ease.in } }}
              className="pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-xl border border-border bg-card p-3.5 shadow-lg"
            >
              <span className={cx('mt-0.5 shrink-0', TONE[t.tone].className)} aria-hidden="true">
                {TONE[t.tone].icon}
              </span>
              <div className="min-w-0 flex-1 text-sm">
                <p className="font-semibold text-foreground">{t.title}</p>
                {t.description && (
                  <p className="mt-0.5 text-muted-foreground [overflow-wrap:anywhere]">{t.description}</p>
                )}
              </div>
              <button
                type="button"
                onClick={() => dismiss(t.id)}
                aria-label="Dismiss notification"
                className="-m-2 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                <CloseIcon className="h-4 w-4" />
              </button>
            </m.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  )
}
