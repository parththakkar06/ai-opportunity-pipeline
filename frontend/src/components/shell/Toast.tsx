import { CircleAlert, CircleCheck, Info, X } from 'lucide-react'
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react'

import { cn } from '@/lib/utils'

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

const ICON = { success: CircleCheck, error: CircleAlert, info: Info }
const TONE = { success: 'text-positive', error: 'text-negative', info: 'text-brand' }
const LIFETIME_MS = { success: 3500, info: 4500, error: 8000 }
const MAX_VISIBLE = 3

/** Short confirmations and errors, bottom-centre. Announced politely to screen readers. */
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
        className="no-print pointer-events-none fixed inset-x-4 bottom-4 z-40 flex flex-col items-center gap-2"
      >
        {toasts.map((t) => {
          const Icon = ICON[t.tone]
          return (
            <div
              key={t.id}
              className="float-in pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-md border border-rule bg-sheet p-3 shadow-float [--origin:bottom_center]"
            >
              <Icon className={cn('mt-0.5 size-4 shrink-0', TONE[t.tone])} strokeWidth={1.5} aria-hidden="true" />
              <div className="min-w-0 flex-1 text-sm">
                <p className="font-medium text-ink">{t.title}</p>
                {t.description && <p className="meta mt-0.5 [overflow-wrap:anywhere]">{t.description}</p>}
              </div>
              <button
                type="button"
                onClick={() => dismiss(t.id)}
                aria-label="Dismiss notification"
                className="-m-1.5 flex size-8 shrink-0 items-center justify-center rounded-md text-ink-3 hover:bg-tint hover:text-ink"
              >
                <X className="size-4" strokeWidth={1.5} aria-hidden="true" />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}
