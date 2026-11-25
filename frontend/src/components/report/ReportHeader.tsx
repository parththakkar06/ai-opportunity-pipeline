import { useState } from 'react'
import type { ReportPayload } from '../../types'
import { useToast } from '../shell/Toast'
import { Badge, Button, CheckIcon, CopyIcon, DownloadIcon, ExternalIcon, PrinterIcon, cx, qualityTone } from '../ui'
import { EmailPanel, ExportMenu } from './ExportMenu'
import { ExternalLink } from './primitives'

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    // Fallback for browsers that block the Clipboard API. It briefly focuses a hidden textarea, so put
    // focus back where it was afterwards (keyboard users would otherwise be dropped at the top of the page).
    const previous = document.activeElement as HTMLElement | null
    const area = document.createElement('textarea')
    area.value = text
    area.setAttribute('readonly', '')
    area.style.position = 'fixed'
    area.style.opacity = '0'
    document.body.appendChild(area)
    area.select()
    const ok = document.execCommand('copy')
    area.remove()
    previous?.focus({ preventScroll: true })
    return ok
  }
}

function download(filename: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/markdown;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

/** Copy / download / prototype actions, shared by the full header and the compact sticky bar. */
export function useReportActions(payload: ReportPayload) {
  const { notify } = useToast()
  const [copied, setCopied] = useState(false)
  const copyPitch = async () => {
    if (!payload.pitch_text) return
    if (await copyText(payload.pitch_text)) {
      setCopied(true)
      notify({ tone: 'success', title: 'CEO pitch copied to the clipboard' })
      window.setTimeout(() => setCopied(false), 1800)
    } else {
      notify({ tone: 'error', title: 'Couldn’t copy', description: 'Your browser blocked clipboard access.' })
    }
  }
  const downloadReport = () => {
    const filename = `${payload.report.slug}-ai-assessment.md`
    download(filename, payload.markdown)
    notify({ tone: 'success', title: 'Report downloaded', description: filename })
  }
  return { copied, copyPitch, downloadReport, canCopy: !!payload.pitch_text }
}

type Actions = ReturnType<typeof useReportActions>

export function ReportActions({
  actions,
  prototypeUrl,
  compact,
  onPrint,
}: {
  actions: Actions
  prototypeUrl: string | null
  compact?: boolean
  onPrint?: () => void
}) {
  return (
    <div className={cx('flex flex-wrap gap-2', compact && 'flex-nowrap')}>
      <Button onClick={actions.copyPitch} disabled={!actions.canCopy} className={compact ? 'px-3' : 'min-w-[8.5rem]'}>
        {actions.copied ? <CheckIcon /> : <CopyIcon />}
        <span className={compact ? 'sr-only lg:not-sr-only' : undefined}>{actions.copied ? 'Copied' : 'Copy pitch'}</span>
      </Button>
      <Button onClick={actions.downloadReport} variant="primary" className={compact ? 'px-3' : undefined}>
        <DownloadIcon />
        <span className={compact ? 'sr-only lg:not-sr-only' : undefined}>Download .md</span>
      </Button>
      {onPrint && (
        <Button onClick={onPrint} className={compact ? 'px-3' : undefined} disabled={!actions.canCopy}>
          <PrinterIcon />
          <span className={compact ? 'sr-only lg:not-sr-only' : undefined}>Print pitch</span>
        </Button>
      )}
      {prototypeUrl && !compact && (
        <a
          href={prototypeUrl}
          target="_blank"
          rel="noreferrer noopener"
          className="inline-flex min-h-11 items-center gap-2 rounded-lg px-4 text-sm font-semibold text-secondary ring-1 ring-border-strong ring-inset hover:bg-subtle"
        >
          <ExternalIcon />
          Prototype<span className="sr-only"> (opens in a new tab)</span>
        </a>
      )}
    </div>
  )
}

export function ReportHeader({ payload, actions, onPrint }: { payload: ReportPayload; actions: Actions; onPrint?: () => void }) {
  const { report } = payload
  const ov = report.company_overview
  const generated = report.generated_at
    ? new Date(report.generated_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
    : null
  const partial = report.stages_completed.length < 4
  const [emailOpen, setEmailOpen] = useState(false)

  return (
    <div className="@container rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-7">
      {/* Laid out by the card's own width (container query), since the sidebar narrows it on desktop. */}
      <div className="flex flex-col gap-5 @3xl:flex-row @3xl:items-start @3xl:justify-between">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold tracking-widest text-accent uppercase">AI opportunity assessment</p>
          <h1
            id="report-title"
            tabIndex={-1}
            translate="no"
            className="mt-1.5 scroll-mt-24 text-3xl font-bold tracking-tight text-foreground sm:text-4xl"
          >
            {report.business_name}
          </h1>
          <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-muted-foreground">
            <span className="font-medium text-secondary">
              {ov.industry}
              {ov.sub_industry ? ` · ${ov.sub_industry}` : ''}
            </span>
            {ov.website && <ExternalLink href={ov.website}>{ov.website.replace(/^https?:\/\//, '').replace(/\/$/, '')}</ExternalLink>}
            {generated && <span>{generated}</span>}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Badge tone={qualityTone(report.data_quality)}>
              {report.data_quality[0].toUpperCase() + report.data_quality.slice(1)} data quality
            </Badge>
            {partial ? (
              <Badge tone="amber">Partial · stages {report.stages_completed.join(', ')} of 4</Badge>
            ) : (
              <Badge tone="green">
                <CheckIcon className="h-3 w-3" /> All 4 stages complete
              </Badge>
            )}
          </div>
        </div>
        <div className="no-print flex shrink-0 flex-wrap gap-2">
          <ReportActions actions={actions} prototypeUrl={payload.prototype_url} onPrint={onPrint} />
          <ExportMenu slug={report.slug} hasPitch={!!report.ceo_pitch} onEmail={() => setEmailOpen(true)} />
        </div>
      </div>
      {emailOpen && (
        <div className="no-print">
          <EmailPanel slug={report.slug} onClose={() => setEmailOpen(false)} />
        </div>
      )}
      {payload.usage && (
        <p className="mt-4 border-t border-border pt-3 text-sm text-muted-foreground tabular-nums">
          This run: {payload.usage.input_tokens.toLocaleString()} input / {payload.usage.output_tokens.toLocaleString()} output
          tokens · cost {payload.usage.cost}
        </p>
      )}
    </div>
  )
}
