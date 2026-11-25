// HTTP Basic Auth check for the team password (used by middleware.ts on Vercel). Pure, so it's unit-tested.

export type AuthResult = 'ok' | 'denied' | 'unconfigured'

/** Compare without stopping at the first differing character. */
function safeEqual(a: string, b: string): boolean {
  let diff = a.length ^ b.length
  const n = Math.max(a.length, b.length)
  for (let i = 0; i < n; i++) diff |= (a.charCodeAt(i) || 0) ^ (b.charCodeAt(i) || 0)
  return diff === 0
}

/**
 * `header` is the request's Authorization header. Fails closed: with no password configured, nobody gets in.
 * Any user name is accepted when `user` is empty; otherwise it must match too.
 */
export function checkBasicAuth(header: string | null | undefined, password: string | undefined, user = ''): AuthResult {
  if (!password) return 'unconfigured'
  const match = /^Basic\s+(.+)$/i.exec(header ?? '')
  if (!match) return 'denied'
  let decoded: string
  try {
    const bytes = Uint8Array.from(atob(match[1]), (c) => c.charCodeAt(0))
    decoded = new TextDecoder().decode(bytes)
  } catch {
    return 'denied'
  }
  const split = decoded.indexOf(':')
  if (split < 0) return 'denied'
  const gotUser = decoded.slice(0, split)
  const gotPassword = decoded.slice(split + 1)
  const userOk = user === '' || safeEqual(gotUser, user)
  return safeEqual(gotPassword, password) && userOk ? 'ok' : 'denied'
}
