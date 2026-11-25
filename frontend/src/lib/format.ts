const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })
const UNITS: Array<[Intl.RelativeTimeFormatUnit, number]> = [
  ['year', 31536000],
  ['month', 2592000],
  ['week', 604800],
  ['day', 86400],
  ['hour', 3600],
  ['minute', 60],
]

/** "3 hours ago", "yesterday", "just now". */
export function relativeTime(iso: string | null): string {
  if (!iso) return ''
  const seconds = (new Date(iso).getTime() - Date.now()) / 1000
  if (!Number.isFinite(seconds)) return ''
  for (const [unit, size] of UNITS) {
    if (Math.abs(seconds) >= size) return rtf.format(Math.round(seconds / size), unit)
  }
  return 'just now'
}

/** "2026-11-25T07:00:00+00:00" -> "25 Nov 2026". */
export function shortDate(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

/** 54321 -> "54.3k". */
export function compact(n: number | null | undefined): string {
  if (n == null) return '—'
  return n >= 1000 ? `${(n / 1000).toFixed(n >= 100_000 ? 0 : 1)}k` : String(n)
}

/** "https://www.Sobha.com/about" → "sobha.com/about"; empty input stays empty. */
export function normalizeWebsite(value: string): string {
  return value.trim().replace(/^https?:\/\//i, '').replace(/^www\./i, '').replace(/\/$/, '').toLowerCase()
}

const DOMAIN = /^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}(\/[^\s]*)?$/i

export function isValidWebsite(value: string): boolean {
  const v = normalizeWebsite(value)
  return v === '' || DOMAIN.test(v)
}
