/**
 * Shared motion tokens (docs/FRONTEND_PLAN.md §6).
 * Rules from the UI/UX skill: one rhythm everywhere, exits about 65% of entries, decelerate in and
 * accelerate out, only opacity and transform, and at most 1–2 animated elements per view.
 * Reduced motion is handled globally by <MotionConfig reducedMotion="user"> in main.tsx.
 */
import type { Transition, Variants } from 'framer-motion'

export const duration = {
  fast: 0.15, // hovers, presses, icon swaps
  base: 0.24, // tab content, cards
  slow: 0.4, // page-level changes, first report entrance
} as const

export const ease = {
  out: [0.22, 1, 0.36, 1], // decelerate on enter
  in: [0.64, 0, 0.78, 0], // accelerate on exit
} as const satisfies Record<string, [number, number, number, number]>

/** Spring for indicators only, such as the active-tab underline. Never used on data. */
export const indicatorSpring: Transition = { type: 'spring', stiffness: 400, damping: 32, mass: 0.8 }

const exit = (d: number) => Math.round(d * 0.65 * 1000) / 1000

/** Fade + small rise. Use for tab panels and freshly loaded content. */
export const fadeRise: Variants = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0, transition: { duration: duration.base, ease: ease.out } },
  exit: { opacity: 0, y: -4, transition: { duration: exit(duration.base), ease: ease.in } },
}

/** Container that staggers its children once, on the first report load only. */
export const staggerOnce: Variants = {
  initial: {},
  animate: { transition: { staggerChildren: 0.04, delayChildren: 0.05 } },
}

export const fadeIn: Variants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: { duration: duration.fast, ease: ease.out } },
  exit: { opacity: 0, transition: { duration: exit(duration.fast), ease: ease.in } },
}
