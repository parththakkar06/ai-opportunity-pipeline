// Static mode: a read-only snapshot with no backend (the Vercel build; see docs/DEPLOY_VERCEL.md).
// Reports and their exports are plain files in /data, produced ahead of time by scripts/build_static.py.
// `npm run build:static` sets VITE_STATIC=1; the normal build and `npm run dev` talk to the API as before.

export const STATIC: boolean = (import.meta as { env?: { VITE_STATIC?: string } }).env?.VITE_STATIC === '1'

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
export function exportUrl(slug: string, kind: ExportKind, staticMode: boolean = STATIC): string {
  const s = encodeURIComponent(slug)
  return staticMode ? `/data/exports/${s}/${STATIC_FILES[kind]}` : `/api/examples/${s}/export/${kind}`
}
