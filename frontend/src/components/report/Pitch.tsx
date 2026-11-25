import { useEffect, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import type { ReportPayload } from '@/types'

import { TracePanel } from './Citations'
import { ExportMenu, exportBase } from './ExportMenu'

const A4 = { width: 794, height: 1123 } // CSS pixels at 96 dpi

/** The real A4 page: the same HTML the one-page PDF prints, scaled to fit the column. */
export function Pitch({ payload, onEmail }: { payload: ReportPayload; onEmail: () => void }) {
  const r = payload.report
  const p = r.ceo_pitch
  const boxRef = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(1)
  const [html, setHtml] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    const el = boxRef.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => setScale(Math.min(1, e.contentRect.width / A4.width)))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // The page is fetched and shown through srcdoc in a fully sandboxed frame: no scripts, no navigation.
  const src = `${exportBase(r.slug)}/pitch.html?v=${encodeURIComponent(r.generated_at ?? '')}`
  useEffect(() => {
    if (!p) return
    const ctrl = new AbortController()
    fetch(src, { signal: ctrl.signal })
      .then((res) => (res.ok ? res.text() : Promise.reject(new Error(res.statusText))))
      .then(setHtml)
      .catch(() => !ctrl.signal.aborted && setFailed(true))
    return () => ctrl.abort()
  }, [src, p])

  if (!p) return <p className="meta">The pitch stage hasn't run for this company yet. Resume the run to write it.</p>
  const v = r.verification

  return (
    <div>
      <div className="no-print mb-5 flex flex-wrap items-center gap-2">
        <Button asChild size="sm">
          <a href={`${exportBase(r.slug)}/pitch.pdf`} download>
            Download PDF
          </a>
        </Button>
        <Button variant="outline" size="sm" onClick={onEmail}>
          Email draft…
        </Button>
        <ExportMenu payload={payload} onEmail={onEmail} />
        <p className="meta ml-auto">Addressed to {p.addressed_to}</p>
      </div>

      <div ref={boxRef} className="max-w-[794px]">
        <div className="relative overflow-hidden p-px" style={{ height: A4.height * scale + 2 }}>
          {!html && (
            <div className="absolute inset-0 flex items-center justify-center rounded-[2px] border border-rule bg-sheet">
              <p className="meta">{failed ? 'The page preview could not be rendered. Use Download PDF.' : 'Rendering the page…'}</p>
            </div>
          )}
          {html && (
            <iframe
              title={`One-page pitch for ${r.business_name} (A4 preview, identical to the PDF)`}
              srcDoc={html}
              sandbox=""
              className="absolute top-0 left-0 origin-top-left rounded-[2px] border border-rule bg-white shadow-float"
              style={{ width: A4.width, height: A4.height, transform: `scale(${scale})` }}
            />
          )}
        </div>
      </div>

      <div className="mt-10 grid max-w-[72ch] gap-10">
        {v && v.pass_rate != null && (
          <section aria-labelledby="verify-heading">
            <h3 id="verify-heading" className="heading text-lg text-ink">
              Verification
            </h3>
            <p className="mt-1 text-[15px] text-ink-2">
              <span className={v.pass_rate >= 0.8 ? 'font-medium text-positive' : 'font-medium text-caution'}>
                {v.supported} of {v.checked} factual claims
              </span>{' '}
              in the pitch match a cited fact.{' '}
              {v.estimates === 1
                ? '1 estimate (a projection or ROI figure) is excluded.'
                : `${v.estimates} estimates (projections and ROI figures) are excluded.`}
            </p>
            {v.actions.length > 0 && (
              <ul className="mt-2 space-y-1 text-sm text-ink-2">
                {v.actions.map((a) => (
                  <li key={a} className="flex gap-2">
                    <span aria-hidden="true" className="text-ink-3">
                      –
                    </span>
                    <span className="min-w-0 [overflow-wrap:anywhere]">{a}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}

        <TracePanel report={r} />

        <details>
          <summary className="heading text-lg text-ink">60-second elevator pitch</summary>
          <p className="prose-serif mt-2 whitespace-pre-line text-ink">{p.elevator_pitch}</p>
        </details>
      </div>
    </div>
  )
}
