import { useSyncExternalStore } from 'react'

/** Live media-query match, e.g. useMediaQuery('(min-width: 1100px)'). */
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

/** Wide enough for the sticky table of contents beside the report. */
export const useIsDesktop = () => useMediaQuery('(min-width: 1100px)')
