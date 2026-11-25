// Static mode: a read-only snapshot with no backend (the Vercel build; see docs/DEPLOY_VERCEL.md).
// Reports and their exports are plain files in /data, produced ahead of time by scripts/build_static.py.
// `npm run build:static` sets VITE_STATIC=1; the normal build and `npm run dev` talk to the API as before.

const env = (import.meta as { env?: Record<string, string | undefined> }).env ?? {}

export const STATIC: boolean = env.VITE_STATIC === '1'

/**
 * Where the API lives. Empty (the default) means the same site, as in local development and on Render. Set
 * VITE_API_BASE to a full address (for example https://my-app.onrender.com) when this front end is hosted
 * separately, as on Vercel; the Render service allows those calls (CORS_ORIGINS).
 */
export const API_BASE: string = (env.VITE_API_BASE ?? '').trim().replace(/\/+$/, '')

export const apiUrl = (path: string, base: string = API_BASE): string => `${base}${path}`

export type ExportKind = 'pitch.pdf' | 'report.pdf' | 'pptx' | 'zip' | 'eml' | 'pitch.html' | 'email'

const STATIC_FILES: Record<ExportKind, string> = {
  'pitch.pdf': 'pitch.pdf',
  'report.pdf': 'report.pdf',
  pptx: 'deck.pptx',
  zip: 'exports.zip',
  eml: 'outreach.eml',
  'pitch.html': 'pitch.html',
  email: 'email.json',
}

/** Where an export lives: the API in the live app, a pre-built file in the static snapshot. */
export function exportUrl(
  slug: string,
  kind: ExportKind,
  staticMode: boolean = STATIC,
  apiBase: string = API_BASE,
): string {
  const s = encodeURIComponent(slug)
  return staticMode ? `/data/exports/${s}/${STATIC_FILES[kind]}` : apiUrl(`/api/examples/${s}/export/${kind}`, apiBase)
}
