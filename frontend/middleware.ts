// Vercel Routing Middleware: asks for the team password before serving anything (the site, /data, downloads).
// Set SITE_PASSWORD in the Vercel project's environment variables (optionally SITE_USER to require a user name).
// With no SITE_PASSWORD it refuses every request rather than leaving the site open.
import { next } from '@vercel/functions'

import { checkBasicAuth } from './src/lib/basicAuth.ts'

export const config = { matcher: '/(.*)' }

export default function middleware(request: Request) {
  const env = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env ?? {}
  const result = checkBasicAuth(request.headers.get('authorization'), env.SITE_PASSWORD, env.SITE_USER ?? '')
  if (result === 'ok') return next()
  if (result === 'unconfigured') {
    return new Response('This site is locked: set SITE_PASSWORD in the Vercel project settings.', {
      status: 503,
      headers: { 'content-type': 'text/plain; charset=utf-8', 'cache-control': 'no-store' },
    })
  }
  return new Response('Password required.', {
    status: 401,
    headers: {
      'www-authenticate': 'Basic realm="Team reports", charset="UTF-8"',
      'content-type': 'text/plain; charset=utf-8',
      'cache-control': 'no-store',
    },
  })
}
