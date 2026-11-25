// The report's single accent: the company's brand colour, adjusted until text in it reads at 4.5:1 on
// both paper and white (light theme) or on the dark surfaces (dark theme). Near-grey or missing colours
// fall back to ink blue. Same rule as utils/export/data.py, so the app and the exports agree.

const INK_BLUE = '#1f3a6e'
const INK_BLUE_DARK = '#8fb0e8'
const LIGHT_BG = ['#fbfaf7', '#ffffff']
const DARK_BG = ['#151518', '#1d1d21']
const MIN = 4.5

const rgb = (h: string) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255)
const hex = (c: number[]) => '#' + c.map((x) => Math.round(Math.min(1, Math.max(0, x)) * 255).toString(16).padStart(2, '0')).join('')

function luminance(h: string): number {
  const [r, g, b] = rgb(h).map((x) => (x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

function adjust(value: string, backgrounds: string[], step: (c: number[]) => number[]): string | null {
  let colour = value.toLowerCase()
  for (let i = 0; i < 40; i++) {
    if (Math.min(...backgrounds.map((b) => contrast(colour, b))) >= MIN) return colour
    colour = hex(step(rgb(colour)))
  }
  return null
}

/** { light, dark } accent values for a brand hex (or the ink-blue fallbacks). */
export function brandAccent(value: string | null | undefined): { light: string; dark: string } {
  if (!value || !/^#[0-9a-f]{6}$/i.test(value)) return { light: INK_BLUE, dark: INK_BLUE_DARK }
  const c = rgb(value)
  if (Math.max(...c) - Math.min(...c) < 0.12) return { light: INK_BLUE, dark: INK_BLUE_DARK }
  return {
    light: adjust(value, LIGHT_BG, (x) => x.map((v) => v * 0.94)) ?? INK_BLUE,
    dark: adjust(value, DARK_BG, (x) => x.map((v) => v + (1 - v) * 0.08)) ?? INK_BLUE_DARK,
  }
}
