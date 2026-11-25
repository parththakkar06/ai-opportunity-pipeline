import assert from 'node:assert/strict'
import { test } from 'node:test'

import { compact, isValidWebsite, normalizeWebsite, shortDate } from '../src/lib/format.ts'

test('normalizeWebsite strips scheme, www and trailing slash', () => {
  assert.equal(normalizeWebsite('https://www.Sobha.com/about/'), 'sobha.com/about')
  assert.equal(normalizeWebsite('  '), '')
})

test('isValidWebsite accepts domains and empty input, rejects junk', () => {
  for (const ok of ['sobha.com', 'www.prestigeconstructions.com', 'acme.co.in/projects', '']) assert.ok(isValidWebsite(ok), ok)
  for (const bad of ['sobha', 'two words.com']) assert.ok(!isValidWebsite(bad), bad)
})

test('compact formats token counts', () => {
  assert.equal(compact(950), '950')
  assert.equal(compact(54_621), '54.6k')
  assert.equal(compact(250_000), '250k')
  assert.equal(compact(null), '—')
})

test('shortDate reads ISO dates and timestamps without shifting the day', () => {
  assert.match(shortDate('2026-03-31'), /31/)
  assert.match(shortDate('2026-11-25T07:00:00+00:00'), /2026/)
  assert.equal(shortDate(null), '')
  assert.equal(shortDate('not a date'), 'not a date')
})
