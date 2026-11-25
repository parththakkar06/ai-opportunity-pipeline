// Email links built in the browser. The live app gets these from the server (utils/export/documents.py);
// the static snapshot has no server, so the same logic lives here. Nothing is ever sent from the app.

const MAILTO_LIMIT = 1800
const SHORTENED_NOTE = '\n\n(The full note is in the attached one-page PDF.)'
const enc = encodeURIComponent

export function gmailUrl(subject: string, body: string, to = ''): string {
  return `https://mail.google.com/mail/?view=cm&fs=1&to=${enc(to)}&su=${enc(subject)}&body=${enc(body)}`
}

/** A mailto: link kept under ~1,800 characters; the body is cut at a sentence if needed. */
export function mailtoUrl(subject: string, body: string, to = '', limit = MAILTO_LIMIT): { url: string; cut: boolean } {
  const recipient = enc(to).replace(/%40/g, '@').replace(/%2C/g, ',')
  const build = (b: string) => `mailto:${recipient}?subject=${enc(subject)}&body=${enc(b)}`
  const full = build(body)
  if (full.length <= limit) return { url: full, cut: false }
  const sentences = body.split(/(?<=[.!?])\s+/)
  while (sentences.length) {
    sentences.pop()
    const url = build(sentences.join(' ') + SHORTENED_NOTE)
    if (url.length <= limit) return { url, cut: true }
  }
  return { url: build('').slice(0, limit), cut: true }
}
