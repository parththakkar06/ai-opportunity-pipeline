import { Monitor, Moon, Sun } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { useTheme, type ThemeChoice } from '@/lib/theme'

const LABELS: Record<ThemeChoice, string> = { system: 'Theme: match system', light: 'Theme: light', dark: 'Theme: dark' }
const ICONS = { system: Monitor, light: Sun, dark: Moon }

/** Cycles system → light → dark. Keyboard-driven and frequent, so it doesn't animate. */
export function ThemeToggle() {
  const { choice, cycle } = useTheme()
  const Icon = ICONS[choice]
  return (
    <Button variant="ghost" size="icon" onClick={cycle} aria-label={`${LABELS[choice]}. Click to change.`} title={LABELS[choice]}>
      <Icon strokeWidth={1.5} aria-hidden="true" />
    </Button>
  )
}
