import { AnimatePresence, m } from 'framer-motion'
import { duration, ease } from '../lib/motion'
import { useTheme, type ThemeChoice } from '../lib/theme'

const LABELS: Record<ThemeChoice, string> = {
  system: 'Theme: match system',
  light: 'Theme: light',
  dark: 'Theme: dark',
}

const ICONS: Record<ThemeChoice, string> = {
  // monitor, sun, moon
  system: 'M3 4h18v12H3zM8 20h8M12 16v4',
  light: 'M12 4V2m0 20v-2m8-8h2M2 12h2m13.66-5.66 1.41-1.41M4.93 19.07l1.41-1.41m0-11.32L4.93 4.93m14.14 14.14-1.41-1.41M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0z',
  dark: 'M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z',
}

/** Cycles system → light → dark. The label states the current choice for screen readers. */
export function ThemeToggle() {
  const { choice, cycle } = useTheme()
  return (
    <button
      type="button"
      onClick={cycle}
      aria-label={`${LABELS[choice]}. Click to change.`}
      title={LABELS[choice]}
      className="inline-flex h-11 w-11 items-center justify-center rounded-lg text-muted-foreground transition-colors duration-150 hover:bg-muted hover:text-foreground"
    >
      <AnimatePresence mode="wait" initial={false}>
        <m.svg
          key={choice}
          className="h-5 w-5"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
          initial={{ opacity: 0, rotate: -30, scale: 0.8 }}
          animate={{ opacity: 1, rotate: 0, scale: 1, transition: { duration: duration.fast, ease: ease.out } }}
          exit={{ opacity: 0, rotate: 30, scale: 0.8, transition: { duration: 0.1, ease: ease.in } }}
        >
          <path d={ICONS[choice]} />
        </m.svg>
      </AnimatePresence>
    </button>
  )
}
