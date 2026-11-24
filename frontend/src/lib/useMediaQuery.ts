import { useSyncExternalStore } from 'react'

/** Live media-query match, e.g. useMediaQuery('(min-width: 1024px)'). */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const media = window.matchMedia(query)
      media.addEventListener('change', onChange)
      return () => media.removeEventListener('change', onChange)
    },
    () => window.matchMedia(query).matches,
    () => false,
  )
}

/** Matches Tailwind's `lg` breakpoint, where the left rail appears. */
export const useIsDesktop = () => useMediaQuery('(min-width: 1024px)')
