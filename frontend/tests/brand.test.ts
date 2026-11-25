// Run with `npm test` (Node's built-in test runner; Node 22.6+ strips the TypeScript types itself).
import assert from 'node:assert/strict'
import { test } from 'node:test'

import { brandAccent, contrast } from '../src/lib/brand.ts'

const LIGHT = ['#fbfaf7', '#ffffff']
const DARK = ['#151518', '#1d1d21']

test('brand accent always reads at 4.5:1 in both themes', () => {
  for (const brand of ['#FFD200', '#E31837', '#0F4C81', '#38BDF8', '#00A86B', '#7B2D8E']) {
    const { light, dark } = brandAccent(brand)
    for (const bg of LIGHT) assert.ok(contrast(light, bg) >= 4.5, `${brand} → ${light} on ${bg}`)
    for (const bg of DARK) assert.ok(contrast(dark, bg) >= 4.5, `${brand} → ${dark} on ${bg}`)
  }
})

test('grey, missing or malformed brand colours fall back to ink blue', () => {
  for (const v of ['#777777', null, undefined, 'teal', '#12345']) assert.equal(brandAccent(v).light, '#1f3a6e')
})

test('matches the Python rule used by the exports (utils/export/data.py)', () => {
  // Python: _hex('#FFD200') == '#897100', _hex('#0F4C81') == '#0F4C81' (already dark enough)
  assert.equal(brandAccent('#FFD200').light, '#897100')
  assert.equal(brandAccent('#0F4C81').light, '#0f4c81')
})
