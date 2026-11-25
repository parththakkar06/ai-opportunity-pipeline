import assert from 'node:assert/strict'
import { test } from 'node:test'

import { gmailUrl, mailtoUrl } from '../src/lib/mail.ts'
import { exportUrl } from '../src/lib/static.ts'

test('export urls: files in static mode, API routes otherwise', () => {
  assert.equal(exportUrl('sobha', 'pitch.pdf', true), '/data/exports/sobha/pitch.pdf')
  assert.equal(exportUrl('sobha', 'pptx', true), '/data/exports/sobha/deck.pptx')
  assert.equal(exportUrl('sobha', 'email', true), '/data/exports/sobha/email.json')
  assert.equal(exportUrl('sobha', 'zip', false), '/api/examples/sobha/export/zip')
  assert.equal(exportUrl('a b', 'eml', true), '/data/exports/a%20b/outreach.eml')
})

test('gmail link carries the recipient, subject and body, and nothing is sent', () => {
  const u = new URL(gmailUrl("Filling Maple Street's chairs", 'Hi Dr. Patel,\n\nHello.', 'ceo@example.com'))
  assert.equal(u.host, 'mail.google.com')
  assert.equal(u.searchParams.get('to'), 'ceo@example.com')
  assert.equal(u.searchParams.get('su'), "Filling Maple Street's chairs")
  assert.equal(u.searchParams.get('body'), 'Hi Dr. Patel,\n\nHello.')
})

test('mailto stays under the length limit, cutting at a sentence when needed', () => {
  const short = mailtoUrl('Hello', 'A short note.', 'a@b.co')
  assert.ok(short.url.startsWith('mailto:a@b.co?subject=Hello') && !short.cut)
  const long = mailtoUrl('Hello', 'This sentence is long enough. '.repeat(200), 'a@b.co')
  assert.ok(long.cut && long.url.length <= 1800 && long.url.startsWith('mailto:a@b.co?'))
  assert.ok(decodeURIComponent(long.url).includes('attached one-page PDF'))
  assert.ok(mailtoUrl('Hello', 'No recipient.').url.startsWith('mailto:?subject='))
})
