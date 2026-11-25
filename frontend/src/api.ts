import { STATIC } from './lib/static'
import type { AnalyzeRequest, Health, ReportPayload, SavedRun, StreamEvent } from './types'

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json()
    if (typeof body?.detail === 'string') return body.detail
    if (Array.isArray(body?.detail)) {
      return body.detail.map((d: { msg?: string }) => d.msg ?? 'Invalid input').join('; ')
    }
  } catch {
    /* not JSON */
  }
  return `Request failed (${res.status} ${res.statusText})`
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) throw new Error(await errorMessage(res))
  return res.json() as Promise<T>
}

// Static snapshot (Vercel): reports are plain files baked in by scripts/build_static.py.
export const fetchHealth = () =>
  STATIC
    ? Promise.resolve<Health>({ status: 'ok', provider: 'static snapshot', llm_key_configured: true, search_provider: '—' })
    : getJSON<Health>('/api/health')
export const fetchRuns = () => getJSON<SavedRun[]>(STATIC ? '/data/examples.json' : '/api/examples')
export const fetchRun = (slug: string) =>
  getJSON<ReportPayload>(STATIC ? `/data/runs/${encodeURIComponent(slug)}.json` : `/api/examples/${encodeURIComponent(slug)}`)

/** POST /api/analyze/stream and parse the Server-Sent Events as they arrive. */
export async function streamAnalyze(
  body: AnalyzeRequest,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  if (STATIC) throw new Error('This is a read-only snapshot of saved reports, so new research can’t be run here.')
  const res = await fetch('/api/analyze/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok || !res.body) throw new Error(await errorMessage(res))

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    let boundary = buffer.indexOf('\n\n')
    while (boundary !== -1) {
      const chunk = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      for (const line of chunk.split('\n')) {
        if (line.startsWith('data: ')) onEvent(JSON.parse(line.slice(6)) as StreamEvent)
      }
      boundary = buffer.indexOf('\n\n')
    }
  }
}
